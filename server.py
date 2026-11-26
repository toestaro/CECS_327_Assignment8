import os
import socket
import zoneinfo
import collections
from datetime import datetime, timezone, timedelta

import psycopg2

# match the strings to the client
Q1 = "What is the average moisture inside our kitchen fridges in the past hours, week and month?"
Q2 = "What is the average water consumption per cycle across our smart dishwashers in the past hour, week and month?"
Q3 = "Which house consumed more electricity in the past 24 hours, and by how much?"

# configurations
# label when sharing is enabled --> database will only have teammate's data after sharing
SHARING_START = None # datetime(2026, 11, 25, 19, 0, tzinfo=timezone.utc)

TABLE = "assignment7_virtual"
LOCAL_HOUSE = "A"  # my house
PEER_HOUSE = "B"   # teammate's house

# DataNiz metadata: sensor's ID --> house, device, and type
SENSORS = [
    # fridge 1
    {"house": "A", "device": "fridge1", "type": "moisture",   "id": 8521, "board": "board_assignment7", "field": "moisture_meter"},
    {"house": "A", "device": "fridge1", "type": "thermistor", "id": 8522, "board": "board_assignment7", "field": "thermistor"},
    {"house": "A", "device": "fridge1", "type": "ammeter",    "id": 8523, "board": "board_assignment7", "field": "ammeter"},
    # fridge 2
    {"house": "A", "device": "fridge2", "type": "moisture",   "id": 8574, "board": "refrigerator2_board", "field": "Moisture Meter - moisture_meter_fridge2"},
    {"house": "A", "device": "fridge2", "type": "thermistor", "id": 8575, "board": "refrigerator2_board", "field": "thermistor_fridge2"},
    {"house": "A", "device": "fridge2", "type": "ammeter",    "id": 8573, "board": "refrigerator2_board", "field": "ammeter_fridge2"},
    # dishwasher
    {"house": "A", "device": "dishwasher", "type": "water",   "id": 8563, "board": "dishwasher_board", "field": "water consumption"},
    {"house": "A", "device": "dishwasher", "type": "ammeter", "id": 8535, "board": "dishwasher_board", "field": "ammeter_dishwasher"},
    # add teammate's IDS
]

# Assumptions
ASSUMED_VOLTS = 120.0        # ammeter gives amps only, so we assume US household voltage
LITERS_TO_GALLONS = 0.264172
MAX_GAP_SECONDS = 300        # readings come every 1 min; a bigger gap means data was missing, so don't count it

PST = zoneinfo.ZoneInfo("America/Los_Angeles")

# using metadata to find one house's sensors of one type
def sensorFor(house, sensorType):
    return [s for s in SENSORS if s["house"] == house and s["type"] == sensorType]

def connection(source):
    # source is "local" (my database) or "peer" (teammate's database)
    url = os.environ.get("LOCAL_DB_URL" if source == "local" else "PEER_DB_URL")
    if not url:
        raise RuntimeError(f"Missing environment variable for the {source} database")
    return psycopg2.connect(url)

# reads one sensor's values between 2 times from either databases
def fetchReadings(source, sensorIds, start, end):
    # if it's read from teammate's database
    if source == "peer":
        origin = "peer-fetched"
    # my database
    elif sensorIds["house"] == LOCAL_HOUSE:
        origin = "local"
    # replicated data from mine and teammate's database
    else:
        origin = "shared-copy"

    # sql query
    query = f"""
        SELECT (payload->>'timestamp')::bigint AS ts, (payload->>%s)::float AS val
        FROM {TABLE} 
        WHERE payload->>'board_name' = %s
          AND (payload->>'timestamp')::bigint >= %s
          AND (payload->>'timestamp')::bigint < %s
          AND payload->>%s IS NOT NULL
        ORDER BY ts
    """

    # running it
    connect = connection(source)
    try:
        curr = connect.cursor()
        curr.execute(query, (sensorIds["field"], sensorIds["board"],
                             int(start.timestamp()), int(end.timestamp()), sensorIds["field"]))
        rows = curr.fetchall()
    finally:
        # close connection even if something goes wrong
        connect.close()

    # clean up
    return [(datetime.fromtimestamp(ts, tz=timezone.utc), val, sensorIds["house"], origin) for ts, val in rows]

def teammateDataWindowComplete(start):
    if SHARING_START is None:
        raise RuntimeError("SHARING_START is not set yet.")
    return start >= SHARING_START

def readingsForSensor(sensor, start, end):
    # my house: everything in my database
    if sensor["house"] == LOCAL_HOUSE:
        return fetchReadings("local", sensor, start, end)

    # teammate's house, where window is complete after sharing: our copy is complete
    if teammateDataWindowComplete(start):
        return fetchReadings("local", sensor, start, end)

    # window starts before sharing: old part from the teammate's database
    # newer part from our copy --> make sure to not overlap and sort separately
    oldPart = fetchReadings("peer", sensor, start, min(end, SHARING_START))
    newPart = []
    if end > SHARING_START:
        newPart = fetchReadings("local", sensor, SHARING_START, end)
    return oldPart + newPart

def getHouseReadings(house, sensorType, start, end):
    readings = []
    for sensor in sensorFor(house, sensorType):
        readings += readingsForSensor(sensor, start, end)
    readings.sort(key=lambda r: r[0])
    return readings

# helpers
def toPST(utcTime):
    return utcTime.astimezone(PST).strftime("%Y-%m-%d %I:%M %p %Z")

def originSummary(readings):
    # e.g. "120 local, 50 peer-fetched" - shows where the data came from
    counts = collections.Counter(r[3] for r in readings)
    return ", ".join(f"{n} {name}" for name, n in counts.items()) or "no data"


def average(readings, unit, factor=1.0):
    if not readings:
        return "no data"
    avg = sum(r[1] for r in readings) / len(readings) * factor
    return f"{avg:.2f} {unit} ({originSummary(readings)})"


def energyKwh(readings):
    # readings = time-sorted (timestamp, amps, ...) from ONE sensor.
    # energy = volts x amps x hours / 1000, between each pair of consecutive readings
    total = 0.0
    for i in range(1, len(readings)):
        seconds = (readings[i][0] - readings[i - 1][0]).total_seconds()
        if seconds > MAX_GAP_SECONDS:
            continue  # data was missing here, don't guess
        avgAmps = (readings[i][1] + readings[i - 1][1]) / 2
        total += ASSUMED_VOLTS * avgAmps * (seconds / 3600) / 1000
    return total


def houseEnergy(house, start, end):
    # energy is computed per ammeter (each is its own time series), then added up per house
    perDevice = {}
    origins = []
    for sensor in sensorFor(house, "ammeter"):
        readings = readingsForSensor(sensor, start, end)
        perDevice[sensor["device"]] = energyKwh(readings)
        origins += readings
    return sum(perDevice.values()), perDevice, origins

# query answers
# WINDOWS: label and length of time (1 hour, 7 days, 30 days)
WINDOWS = [
    ("past hour", timedelta(hours=1)),
    ("past week", timedelta(days=7)),
    ("past month", timedelta(days=30))
]

# each window, each house, gets readings and averages them
def averageByWindow(title, sensorType, unit, factor=1.0):
    now = datetime.now(timezone.utc)
    lines = [f"{title}, as of {toPST(now)}:"]
    for label, length in WINDOWS:
        parts = []
        for house in (LOCAL_HOUSE, PEER_HOUSE):
            readings = getHouseReadings(house, sensorType, now-length, now)
            parts.append(f"House {house}: {average(readings, unit, factor)}")
        lines.append(f"{label}: " + " | ".join(parts))
    return "\n".join(lines)

def handleFridgeMoisture():
    return averageByWindow("Average fridge moisture", "moisture", "V")

def handleDishwasherWater():
    return averageByWindow("Average dishwasher water consumption", "water", "gal", LITERS_TO_GALLONS)

def handleElectricityComparison():
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=24)
    results = {house: houseEnergy(house, start, now) for house in (LOCAL_HOUSE, PEER_HOUSE)}

    lines = [f"Electricity use, past 24 hours (as of {toPST(now)}), assuming {ASSUMED_VOLTS:.0f} V:"]
    for house, (total, perDevice, readings) in results.items():
        devices = ", ".join(f"{d} {kwh:.3f}" for d, kwh in perDevice.items()) or "no sensors configured"
        lines.append(f"  House {house}: {total:.3f} kWh ({devices}) [{originSummary(readings)}]")

    totalA, totalB = results[LOCAL_HOUSE][0], results[PEER_HOUSE][0]
    if totalA == totalB:
        lines.append("Both houses used the same amount.")
    else:
        higher = LOCAL_HOUSE if totalA > totalB else PEER_HOUSE
        lines.append(f"House {higher} used more, by {abs(totalA - totalB):.3f} kWh.")

    # if there's no data in the readings for the houses
    if any(not readings for _, _, readings in results.values()):
        lines.append("  Note: a house has no data in this window, so the comparison is incomplete.")
    return "\n".join(lines)

QUERY_HANDLERS = {
    Q1: handleFridgeMoisture,
    Q2: handleDishwasherWater,
    Q3: handleElectricityComparison
}

def processQuery(query):
    handler = QUERY_HANDLERS.get(query)
    # check if user uses the correct query questions
    if handler is None:
        return "Sorry, this query cannot be processed. Please try one of the supported queries."
    return handler()


def main():
    # allow user to input port number
    port = int(input("Enter port number of the server: "))
    mySocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    mySocket.bind(("0.0.0.0", port))
    mySocket.listen(5)
    print(f"Server is listening on port {port}...")
    incomingSocket, incomingAddress = mySocket.accept()

    while True:
        # receive data from client
        data = incomingSocket.recv(1024)

        # if bytes is empty = client disconnected
        if not data:
            print(f"{incomingAddress} is disconnected...")
            break

        # turn bytes --> string --> uppercase
        query = data.decode('utf-8')
        print(f"Received: {query}")

        # process queries
        try:
            response = processQuery(query)
        except Exception as e:
            response = f"Server error while processing the query: {e}"

        # respond to client with data
        incomingSocket.send(bytearray(response, encoding='utf-8'))

    incomingSocket.close()

if __name__ == '__main__':
    main()
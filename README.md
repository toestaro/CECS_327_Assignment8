# CECS_327_Assignment8
Team #7: Tara Nguyen and Mindy Yun

A TCP client/server system that answers questions about two smart houses (A and B). Each of us owns one house, with our own DataNiz and our own database. For example, House A is me, and House B is Mindy's. DataNiz sharing copies of each house's future data into the other's database, so every database holds only a small view of the combined data. The server works out what's missing and fetches it from the teammate's original database.

# Supported Queries:
The client accepts only these three queries (capitalization and "?" are ignored). Anything else is rejected and never sent to the server.
1. What is the average moisture inside our kitchen fridges in the past hours, week and month?
2. What is the average water consumption per cycle across our smart dishwashers in the past hour, week and month?
3. Which house consumed more electricity in the past 24 hours, and by how much?

# Set up
pip install -r requirements.txt

# Configuration
You would need to set up a database connection for your local database and your teammate's database in CMD (Windows).

Inside CMD:

set "LOCAL_DB_URL=postgresql..."

set "PEER_DB_URL=postgresql..."


# Running
1. Start the server, then enter a port (ex. 5000)
2. In a second window (or your teammate), start the client. Enter the server's IP and the same port as the server.
3. Type one of the three supported queries. Type "quit" to exit.

# How the system connects and retrieves data
- connect(source) opens a PostgreSQL connection to either "local" or "peer" database, using the matching environment variable.
- fetchReadings(source, sensorIds, start, end) reads one sensor's values for start <= time < end. Each row's JSON payload holds a timestamp, a board_name, and one field per reading. The query filters by board and time range and extracts the field named in the sensor's metadata
- Every reading returns as (timestamp, value, house, origin), so ownership and source are preserved after data is combined. origin in one of:

  - local: my house, reads from my database
  - shared-copy: teammate's house, read from my database (it's replicated by DataNiz sharing)
  - peer-fetched: teammate's house, read from their database

# How distributed query works
readingsForSensor() decides where each sensor's data comes from:
1. My house
2. Teammate's house, window starts at or after SHARING_START: when local copy is complete, so it reads from the local database
3. Teammate's house, window starts before SHARING_START: reads the old part from the teammate's database, read the rest from the local copy, and joins the two lists

# How query completeness is determined
Local database holds my teammate's data only from SHARING_START onward. isWindowComplete(start) returns only true if the query window starts at or after SHARING_START. If it returns false, then the window reaches into the pre-sharing period, and the missing part is fetched from the teammate's database (case 3 above). 

# How DataNiz metadata and sharing are used
Each entry of SENSORS is built from DataNiz metadata:
- house: separates House A and House B
- device: separates the fridges and dishwasher
- type: maps differently named sensors to one kind (ammeter and ammeter_fridge2 == ammeter)
- id: DataNiz sensor ID
- board and field: says where readings live in the stored payload
- origin: tag on each reading records whether it's local, a shared copy, or fetched from the teammate.

DataNiz Sharing: 

DataNiz sharing is forward-only: once a sensor is shared, new readings are replicated into the receiving user's database, but older readings are not.
The server is built around this. SHARING_START marks when replication began; for windows that start earlier, the missing part of the teammate's history is fetched from their original database (PEER_DB_URL), and the rest is read from the local copy.

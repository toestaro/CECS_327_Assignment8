import socket

# three queries client will accept --> users must type this out
Q1 = "What is the average moisture inside our kitchen fridges in the past hours, week and month?"
Q2 = "What is the average water consumption per cycle across our smart dishwashers in the past hour, week and month?"
Q3 = "Which house consumed more electricity in the past 24 hours, and by how much?"

# dictionary
# key = user will type (lowercase, no ?, single spaces)
# value = official query (Q1, Q2, Q3) that gets sent to the server
ACCEPTED_QUERIES = {
    "what is the average moisture inside our kitchen fridges in the past hours, week and month" : Q1,
    "what is the average water consumption per cycle across our smart dishwashers in the past hour, week and month" : Q2,
    "which house consumed more electricity in the past 24 hours, and by how much" : Q3
}

REJECT_MESSAGE = "Sorry, this query cannot be processed. Please try one of the supported queries."

# normalize the query that user provide to match ACCEPTED_QUERIES
def normalizeQuery(text):
    text = text.strip().lower().rstrip("?").strip()
    return " ".join(text.split())

def supportedQueryMessage():
    print(f"Supported Queries: \n    1. {Q1}\n    2. {Q2}\n    3. {Q3}")

def main():
    # have user input their IP address and port number
    # display error message for IP address if entered incorrectly
    serverIP = input("Enter the IP address of the server: ").strip()
    try:
        socket.inet_aton(serverIP)
    except OSError:
        print("Error: invalid IP address.")
        return

    # display error message for port number if entered incorrectly
    try:
        serverPort = int(input("Enter the port number of the server: "))
        if not (1 <= serverPort <= 65535):
            raise ValueError
    except ValueError:
        print("Error: port must be in between 1 and 65535.")
        return

    mySocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    mySocket.settimeout(5)  # timeout so that wrong IP won't hang for a long time
    try:
        mySocket.connect((serverIP, serverPort))
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        print(f"Error: could not connect to {serverIP}:{serverPort} ({e})")
        return
    mySocket.settimeout(None)
    print("It is connected...")

    # once it is connected to the other person, print the supportedQueryMessage()
    supportedQueryMessage()

    while True:
        # ask user to enter a message to send to the server
        message = input("Enter a message to send (or 'quit' to exit): ")
        if message == 'quit':
            print("Quitting the message...")
            break

        if message == "":
            print("Please type something to send.")
            continue

        # only allow 3 supported queries; reject everything else WITHOUT contacting server
        query = ACCEPTED_QUERIES.get(normalizeQuery(message))
        if query is None:
            print(REJECT_MESSAGE)
            supportedQueryMessage()
            continue

        mySocket.send(bytearray(message, encoding='utf-8'))
        myData = mySocket.recv(1024)
        if not myData:
            print("Server closed the connection.")
            break

        serverResponse = myData.decode('utf-8')
        print(f"Server response: {serverResponse}")

    mySocket.close()

if __name__ == '__main__':
    main()
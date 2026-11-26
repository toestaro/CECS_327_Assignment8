# CECS_327_Assignment8
Team #7: Tara Nguyen and Mindy Yun

A TCP client/server system that answers questions about two smart houses (A and B). Each of us owns one house, with our own DataNiz and our own database. For example, House A is me, and House B is Mindy's. DataNiz sharing copies of each house's future data into the other's database, so every database holds only a small view of the combined data. The server works out what's missing and fetches it from the teammate's original database.

# Supported Queries:
The client accepts only these three queries (capitalization and "?" are ignored). Anything else is rejected and never sent to the server.
1. What is the average moisture inside our kitchen fridges in the past hours, week and month?
2. What is the average water consumption per cycle across our smart dishwashers in the past hour, week and month?
3. Which house consumed more electricity in the past 24 hours, and by how much?

# Configuration
You would need to set up a database connection for your local database and your teammate's database in CMD (Windows).
Inside CMD:
set "LOCAL_DB_URL=postgresql..."
set "PEER_DB_URL=postgresql..."

# Running
1. Start the server, then enter a port (ex. 5000)
2. In a second window (or your teammate), start the client. Enter the server's IP and the same port as the server.
3. Type one of the three supported queries. Type "quit" to exit.

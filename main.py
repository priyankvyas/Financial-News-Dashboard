# Import the relevant libraries
import constants
import requests
import time
from pymongo import MongoClient

# URI for the MongoDB cluster that is used for data storage
database_uri = 'mongodb+srv://{0}:{1}@{2}/?retryWrites=true&w=majority'.format(constants.MONGO_USERNAME,
                                                                               constants.MONGO_PASSWORD,
                                                                               constants.MONGO_CLUSTER)

# While loop to set the one-week period for data collection. We check if the script is active in this time period and
# once a week's worth of data is collected, the script terminates. The time period here is 2nd December 2024 to 10th
# December 2024.
while time.time() < 1733848300:
    if time.time() >= 1733152200:

        # Try clause to handle any exceptions during runtime
        try:

            # Initialize the MongoDB client
            client = MongoClient(database_uri)
            print("Connected to MongoDB successfully!")

            # Access the iot_data database from the cluster. If there is no database with this name, a new database is
            # created
            db = client["iot_data"]

            # Access the AAPL_intraday_data collection in the database. If there is no collection with this name, a new
            # collection is created
            ticker_collection = db["AAPL_intraday_data"]

            # Send a GET request to the Alpha Vantage API to retrieve the AAPL intraday data. The interval is set to 5
            # minutes and the extended hours trade information is set to false. We only collect data for the stock price
            # of Apple when the market is open.
            ticker_url = ('https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=AAPL&interval=5min&'
                          'apikey={0}&extended_hours=false'.format(constants.ALPHA_API_KEY))
            ticker_response = requests.get(ticker_url)
            ticker_data = ticker_response.json()

            # Insert the collected JSON into the collection. The schema for the JSON is kept in its original form. We
            # will perform the preprocessing during the analysis stage.
            ticker_collection.insert_one(ticker_data)

            # Access the AAPL_news collection in the database. If there is no collection with this name, a new
            # collection is created
            news_collection = db["AAPL_news"]

            # Send a GET request to the Alpha Vantage API to retrieve AAPL news data. The API endpoint returns the most
            # current 50 news articles that are associated with the company
            news_url = 'https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=AAPL&apikey={0}'.format(
                constants.ALPHA_API_KEY)
            news_response = requests.get(news_url)
            news_data = news_response.json()

            # Insert the collected JSON into the collection. The schema for the JSON is kept in its original form. We
            # will perform the preprocessing during the analysis stage.
            news_collection.insert_one(news_data)

            # We set a timer to have the script wait for 120 minutes before collecting data again. We do this because of
            # the rate limit on the number of requests allowed per day with free access to the API
            time.sleep(7200)

        # Catch any exceptions thrown when performing the data collection and print it to the console for reference
        except Exception as ex:
            print("Error connecting to MongoDB:", ex)

    # When the time interval we are collecting data for has not begun, we continue checking every second to check if we
    # are within the time interval
    else:
        time.sleep(1)

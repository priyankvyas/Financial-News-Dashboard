# Import relevant libraries
import pandas as pd
import streamlit as st
import altair as alt
import matplotlib.pyplot as plt
import pymongo
from wordcloud import WordCloud, STOPWORDS

print(st.secrets.get("MONGO_USERNAME"))

# Prepare the DataFrame for financial news data
def prepare_news_data(cursor):

    # List to store the articles in the DataFrame
    news = []

    # For each entry in the database
    for document in cursor:

        # Check if the document has the "feed" key. When a request fails, the retrieved document only has an error
        # message field, so we check if the document has a key that would only be present in a valid document
        if "feed" in document:
            for article in document["feed"]:

                # Parse the author field into a string
                authors = ""
                for author in article["authors"]:
                    authors += author + ","
                authors = authors[:-1]
                article["authors"] = authors

                # Extract the ticker_sentiment for the chosen ticker symbol
                for ticker in article["ticker_sentiment"]:
                    if ticker["ticker"] == chosen_ticker:
                        article["ticker"] = ticker["ticker"]
                        article["relevance_score"] = ticker["relevance_score"]
                        article["ticker_sentiment_score"] = ticker["ticker_sentiment_score"]
                        article["ticker_sentiment_label"] = ticker["ticker_sentiment_label"]
                del article["ticker_sentiment"]

                # Unwrap the topics and add them as columns
                for topic in article["topics"]:
                    article[topic["topic"]] = topic["relevance_score"]
                del article["topics"]

                # Add columns for the missing topics in this article
                for topic in supported_topics:
                    if topic not in article:
                        article[topic] = 0.00

                # Append the article to the list
                news.append(article)

    # Create a DataFrame from the news collection
    news = pd.DataFrame(news, index=list(range(len(news))))

    # Drop duplicate news article entries from the DataFrame. We check if the article was published at the same time,
    # the same authors, and the same news source
    news.drop_duplicates(subset=["time_published", "authors", "source"], inplace=True, ignore_index=True)

    # Convert the relevance and sentiment score columns to a numeric column
    news["relevance_score"] = pd.to_numeric(news["relevance_score"])
    news["ticker_sentiment_score"] = pd.to_numeric(news["ticker_sentiment_score"])

    # Filter out the articles that have a relevance score less than 0.25
    news = news[news["relevance_score"] >= 0.25]

    # Create a column for the time to be formatted in the same format as the stock data and round it down to 5 minute
    # intervals
    news["formatted_time"] = pd.to_datetime(news["time_published"], format='%Y%m%dT%H%M%S').dt.ceil('5min')

    # print(news.to_markdown())
    return news


# Prepare the DataFrame for intraday stock price information
def prepare_intraday_data(cursor):

    # List to store the stock price in the DataFrame
    intraday = []

    # For each entry in the database
    for document in cursor:

        # Check if the document has the "Meta Data" key. When a request fails, the retrieved document only has an error
        # message field, so we check if the document has a key that would only be present in a valid document
        if "Meta Data" in document:
            for closing_time in document["Time Series (5min)"]:
                price_information = document["Time Series (5min)"][closing_time]
                price_information["closing_time"] = closing_time

                # Rename the key names for the price information
                price_information["open"] = price_information.pop("1. open")
                price_information["high"] = price_information.pop("2. high")
                price_information["low"] = price_information.pop("3. low")
                price_information["close"] = price_information.pop("4. close")
                price_information["volume"] = price_information.pop("5. volume")

                # Append the price information to the list
                intraday.append(price_information)

    # Create a DataFrame from the intraday collection
    intraday = pd.DataFrame(intraday, index=list(range(len(intraday))))

    # Drop duplicate price information entries from the DataFrame. We check if the closing time is the same for entries
    intraday.drop_duplicates(subset=["closing_time"], inplace=True, ignore_index=True)

    # Convert the close price and open price columns to numeric columns
    intraday["close"] = pd.to_numeric(intraday["close"])
    intraday["open"] = pd.to_numeric(intraday["open"])

    # Create a column to measure the change in price for a particular time interval
    intraday["change"] = (intraday["close"] - intraday["open"])/intraday["open"]

    # Convert the closing_time column to the date_time format
    intraday["closing_time"] = pd.to_datetime(intraday["closing_time"])

    # print(intraday.to_markdown())
    return intraday


# Create the dual axis line chart for stock price and news sentiment score
def create_line_chart(merged):

    # Create the base plot with X axis as the closing time
    base = alt.Chart(merged).encode(
        x=alt.X('closing_time')
    ).properties(height=400)

    # Create the first Y axis for the news sentiment score
    sentiment = base.mark_line(stroke='#57A44C', interpolate="step-after").encode(
        y=alt.Y('ticker_sentiment_score', scale=alt.Scale(domain=[-0.2, 0.6]))
        .axis(title='News Sentiment Score', titleColor='#57A44C')
    )

    # Create the second Y axis for the stock closing price
    stock = base.mark_line(stroke='#5276A7', interpolate="step-after").encode(
        y=alt.Y('close', scale=alt.Scale(domain=[236.5, 247.5]))
        .axis(title='Closing price', titleColor='#5276A7')
    )

    # Highlight points with high positive or negative sentiment scores
    highlights = base.mark_circle(size=100, color='red').encode(
        y=alt.Y('ticker_sentiment_score', scale=alt.Scale(domain=[-0.2, 0.6])).axis(None),
        tooltip=['title']
    ).transform_filter(
        (alt.datum.ticker_sentiment_score >= 0.5) | (alt.datum.ticker_sentiment_score <= -0.5)
    )

    # Return the graph with the two Y axes being independent of each other
    return (alt.layer(stock, sentiment, highlights).interactive()
            .resolve_scale(y='independent'))


# Function to create a scatter plot with stock closing price on the Y axis and sentiment score on the X axis
def create_scatter_plot(merged):

    # Create a scatter plot with sentiment score as the X axis and stock price as the Y axis
    scatter_plot = alt.Chart(merged).mark_circle(size=100).encode(
        x=alt.X('ticker_sentiment_score').axis(title='News Sentiment Score'),
        y=alt.Y('close', scale=alt.Scale(domain=[236.5, 247.5])).axis(title="Closing price")
    ).properties(height=400)

    # Create a line of best fit to visualize the trend between ticker_sentiment_score and closing price
    best_fit_line = alt.Chart(merged).transform_regression(
        'ticker_sentiment_score', 'close', method='linear'
    ).mark_line(color='red').encode(
        x='ticker_sentiment_score',
        y='close'
    )

    # Return the combined graph
    return scatter_plot + best_fit_line


# Function to generate a wordcloud for articles that have a positive sentiment
def create_positive_wordcloud(merged):

    # Filter the positive new articles
    positive_merged = merged[merged['ticker_sentiment_score'] > 0.15]

    # Create a joined piece of text containing all the article summaries and titles
    text = ' '.join(positive_merged["summary"]) + ' ' + ' '.join(positive_merged["title"])

    # Create a list of commonly occurring words in the text that are not relevant
    stopwords = ["Apple", "AAPL", "Inc", "NASDAQ"] + list(STOPWORDS)

    # Generate a wordcloud using the article summaries and their titles
    wordcloud = (WordCloud(height=400, background_color="white", stopwords=set(stopwords), colormap="Greens")
                 .generate(text))
    figure, ax = plt.subplots(figsize=(5, 4))
    ax.imshow(wordcloud, interpolation="bilinear")
    ax.axis("off")

    # Return the subplot with the wordcloud
    return figure


# Function to generate a wordcloud for articles that have a negative sentiment
def create_negative_wordcloud(merged):

    # Filter the positive new articles
    negative_merged = merged[merged['ticker_sentiment_score'] < -0.15]

    # Create a joined piece of text containing all the article summaries and titles
    text = ' '.join(negative_merged["summary"]) + ' ' + ' '.join(negative_merged["title"])

    # Create a list of commonly occurring words in the text that are not relevant
    stopwords = ["Apple", "AAPL", "Inc", "NASDAQ"] + list(STOPWORDS)

    # Generate a wordcloud using the article summaries and their titles
    wordcloud = (WordCloud(height=400, background_color="white", stopwords=set(stopwords), colormap="Reds")
                 .generate(text))
    figure, ax = plt.subplots(figsize=(5, 4))
    ax.imshow(wordcloud, interpolation="bilinear")
    ax.axis("off")

    # Return the subplot with the wordcloud
    return figure


# Chosen ticker symbol for analysis
chosen_ticker = "AAPL"

# List of supported topics the articles are classified into
supported_topics = ["Blockchain", "Earnings", "IPO", "Mergers & Acquisitions", "Financial Markets",
                    "Economy - Fiscal Policy", "Economy - Monetary", "Economy - Macro",
                    "Energy & Transportation", "Finance", "Life Sciences", "Manufacturing",
                    "Real Estate & Construction", "Retail & Wholesale", "Technology"]

# URI for the MongoDB cluster that is used for data storage
database_uri = 'mongodb+srv://{0}:{1}@{2}/?retryWrites=true&w=majority'.format(st.secrets.get("MONGO_USERNAME"),
                                                                               st.secrets.get("MONGO_PASSWORD"),
                                                                               st.secrets.get("MONGO_CLUSTER"))

# Try clause for connecting to the database
try:
    client = pymongo.MongoClient(database_uri)

    # Access the iot_data database from the cluster
    db = client["iot_data"]

    # Access the AAPL_intraday_data collection in the database
    ticker_collection = db["AAPL_intraday_data"]

    # Access the AAPL_news collection in the database
    news_collection = db["AAPL_news"]

    # Get all the documents in the collection
    news_cursor = news_collection.find()

    # Preprocess the news data
    news_data = prepare_news_data(news_cursor)

    # Get all the documents in the collection
    intraday_cursor = ticker_collection.find()

    # Preprocess the intraday data
    intraday_data = prepare_intraday_data(intraday_cursor)

    # Merge both the dataframes on the time intervals
    merged_data = pd.merge_asof(
        intraday_data.sort_values('closing_time'),
        news_data.sort_values('formatted_time'),
        left_on='closing_time',
        right_on='formatted_time',
        direction='backward'
    )

    # Set up the page configuration for the dashboard
    st.set_page_config(
        page_title="Financial News Analysis Dashboard",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Create a sidebar for the dashboard
    with st.sidebar:

        # Set the title for the dashboard
        st.title('Financial News Dashboard')

        # Create a list of ticker symbols for which the user wishes to see the financial news and stock price analysis
        ticker_list = ["AAPL"]

        # Create a drop-down box to allow users to select their preferred ticker
        selected_ticker = st.selectbox('Select a ticker symbol', ticker_list, index=0)

    # Create the layout for the dashboard with three columns. The width of the first column is wider than the other two
    # columns
    col = st.columns((5, 5), gap='medium')

    # Add the graphs and visualizations to be shown in the first column
    with col[0]:
        st.markdown('#### Stock Closing Price and News Sentiment Score over time intervals (5 min)')
        line = create_line_chart(merged_data)
        st.altair_chart(line, use_container_width=True)

        st.markdown('#### Bullish wordcloud generated using news article summaries and titles')
        cloud = create_positive_wordcloud(merged_data)
        st.pyplot(cloud)

    # Add the graphs and visualizations to be shown in the second column
    with col[1]:
        st.markdown('#### Stock Closing Price versus News Sentiment Score with Best-Fit line')
        scatter = create_scatter_plot(merged_data)
        st.altair_chart(scatter, use_container_width=True)

        st.markdown('#### Bearish wordcloud generated using news article summaries and titles')
        cloud = create_negative_wordcloud(merged_data)
        st.pyplot(cloud)

# Except clause for handling any runtime exceptions
except Exception as ex:
    print("Error in connecting to the database:", ex)

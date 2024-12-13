# Financial News Dashboard

The dashboard is currently hosted on https://financial-news-dashboard.streamlit.app/

## To run the dashboard locally on your machine:  
Set up a virtual environment using the following command:
```commandline
virtualenv iot-venv
```
Activate the virtual environment  
For Windows
```commandline
iot-venv\Scripts\activate
```
For Mac/Linux
```shell
source iot-venv/Scripts/activate
```
Once the virtual environment is activated, install the dependencies for the project
```commandline
pip install -r requirements.txt
```
To run the python script for collecting data from the Alpha Vantage API, use
```commandline
python main.py
```
To run the dashboard locally, create the .streamlit directory in the project and add the secrets.toml file with the API key for Alpha Vantage and a MongoDB username, password, and cluster address.  
Once complete, the dashboard can be run locally using
```commandline
streamlit run analysis.py
```
#*****************************
#IMPORT packages
#*****************************
# In[1]:
import os, types
import pandas as pd
import os
import getpass
import os, types
import pandas as pd
from botocore.client import Config
import ibm_boto3
# Import environment loading library
from dotenv import load_dotenv
# Import streamlit for the UI 
import streamlit as st
from streamlit_tags import st_tags, st_tags_sidebar


#*****************************
#FUNCTIONS definitions
#*****************************
def __iter__(self): return 0

# In[2]:
def list_classified_files(directory):
    # List to hold file names without the suffix
    classified_files = []

    # Iterate through the files in the given directory
    for filename in os.listdir(directory):
        # Check if the file ends with "_classified.csv"
        if filename.endswith("_classified.csv"):
            # Remove the suffix and add to the list
            file_base_name = filename[:-15]  # "_classified.csv" has 15 characters
            classified_files.append(file_base_name)

    return classified_files


def list_summary_files(directory):
    # List to hold file names without the suffix
    summary_files = []

    # Iterate through the files in the given directory
    for filename in os.listdir(directory):
        # Check if the file ends with "_classified.csv"
        if filename.endswith("_summary.csv"):
            # Remove the suffix and add to the list
            file_base_name = filename[:-12]  # "_summary.csv" has 12 characters
            summary_files .append(file_base_name)

    return summary_files

def search_bucket_contents(bucket_name, search_string):
    print("Retrieving bucket contents from: {0}".format(bucket_name))
    try:
        output=[]
        files = cos_client.list_objects(Bucket=bucket_name)
        for file in files.get("Contents", []):
            print("Item: {0} ({1} bytes).".format(file["Key"], file["Size"]))
            if search_string in file["Key"]:
                output.append(file["Key"])
    except Exception as e:
        print("Unable to retrieve bucket contents: {0}".format(e))
    return output

# In[7]:
def get_credentials():
	return {
		"url" : "https://us-south.ml.cloud.ibm.com",
		"apikey" : API_KEY
	}

def build_text(category):
    messagesCategoryDF=tweetDFclassified[tweetDFclassified['class'] == category]
    return "\n\n".join(messagesCategoryDF['tweet'])
    
def build_prompt(text):
    
    prompt_input = f"""
    You are a gentle bot that build a factsheet for a person. Your task is to combine all the messages from this single person provided between 
    "START OF MESSAGES:" and "END OF MESSAGES" to reflect the thoughts of this person. Ensure your answer includes only the information present in the messages.
    You have to use 'he' when you refer to this person. Include all the details like names, dates, location that are included in the messages.
    Only uses english words in your answer. Do not use code in the answer.

    START OF MESSAGES:
    {text}
    END OF MESSAGES

    Output:
    """
    
    return prompt_input

def concatenate_tweets(df, horizon, max_words=5000):
    tweets = df['tweet'].head(horizon).tolist()
    dates = df['date'].head(horizon).tolist()
    
    zipped_list = list(zip(tweets, dates))
    
    result = []
    current_string = ""
    current_word_count = 0
    start_date = None

    for index, dated_tweet in enumerate(zipped_list):
        tweet = dated_tweet[0]
        tweet_word_count = len(tweet.split())
        if current_word_count + tweet_word_count > max_words:
            end_date = zipped_list[index - 1][1] if index > 0 else dated_tweet[1]
            result.append([current_string.strip(), start_date, end_date])
            current_string = tweet
            current_word_count = tweet_word_count
            start_date = dated_tweet[1]
        else:
            if current_string:
                current_string += "\n\n" + tweet
            else:
                current_string = tweet
                start_date = dated_tweet[1]
            current_word_count += tweet_word_count

    if current_string:
        end_date = zipped_list[-1][1]
        result.append([current_string.strip(), start_date, end_date])
    
    return result

# add missing __iter__ method, so pandas accepts body as file-like object
#if not hasattr(body, "__iter__"): body.__iter__ = types.MethodType( __iter__, body )

#***********************************************************
#PROGRAM START : Load Environments variables from .env file
#***********************************************************

# Load environment vars
load_dotenv()

IBM_API_KEY_ID= os.getenv('IBM_API_KEY_ID')
IBM_AUTH_ENDPOINT= os.getenv('IBM_AUTH_ENDPOINT')
COS_ENDPOINT_URL= os.getenv('COS_ENDPOINT_URL')
BUCKET_NAME= os.getenv('BUCKET_NAME')
API_KEY= os.getenv('API_KEY')
PROJECT_ID= os.getenv('PROJECT_ID')

# @hidden_cellhttps://dataplatform.cloud.ibm.com/analytics/notebooks/v2/3f5d4d50-acac-4118-b514-108367a38304?projectid=ebb779b7-433c-4576-993f-631914c5044f&context=wx#
# The following code accesses a file in your IBM Cloud Object Storage. It includes your credentials.
# You might want to remove those credentials before you share the notebook.

#***********************************************************
#PROGRAM START : Initialize COS, categories, model
#***********************************************************

cos_client = ibm_boto3.client(service_name='s3',
    ibm_api_key_id=IBM_API_KEY_ID,
    ibm_auth_endpoint=IBM_AUTH_ENDPOINT,
    config=Config(signature_version='oauth'),
    endpoint_url=COS_ENDPOINT_URL)

categories={'Technology','Healthcare','Finance','Education','Retail','Entertainment','Travel and Hospitality','Automotive','Real Estate','Energy','Government and Public Services',
            'Environment','Food and Beverage','Manufacturing','Legal','Human Resources','Sport','OTHER'}


# In[8]:
#model_id = "meta-llama/llama-3-8b-instruct"
model_id = "meta-llama/llama-3-70b-instruct"
parameters = {
    "decoding_method": "greedy",
    "max_new_tokens": 4096,
    "repetition_penalty": 1
}

# In[11]:
PROJECT_ID = os.getenv("PROJECT_ID")
space_id = None

from ibm_watsonx_ai.foundation_models import Model
model = Model(
	model_id = model_id,
	params = parameters,
	credentials = get_credentials(),
	project_id = PROJECT_ID,
	space_id = space_id
	)

#***********************************************************
#PROGRAM Main execution Flow : 
#***********************************************************

# Title for the app, size of the page, adding slider widget: 
st.set_page_config(layout="wide")
st.title('🤖 Twacan X Assistant')
horizon_tweets = st.slider("Search History (#tweets): ", 1, 365, 10)

# Get the list of input data from COS (classified files)
listOfTwitterFiles = search_bucket_contents(BUCKET_NAME,"_classified.csv")
listOfTwittos= [w[:-15] for w in listOfTwitterFiles]

# Input widget listing twitter accounts retrieved in COS, classified files. The output is a list of X accounts
twittosSelected = st_tags(
    label='### Search in your X / Twitter network! ',
    text='Add X/Twitter accounts here',
    value= listOfTwittos,
    suggestions=listOfTwittos,
    maxtags = 1,
    key='1')

# setting the button
btn=st.button("Summarize")

resultsDF = pd.DataFrame(columns=['class', 'summary', 'start-date', 'end_date'])

# if the button is pushed
if btn:
  
    twittos=twittosSelected[0]
    txt='Generating summary for'+twittos+' for '+str(horizon_tweets)+' tweets...'
    st.write(txt)
    
    directory_path = '.'
    summary_files_list = list_summary_files(directory_path)
    print(summary_files_list)
    
    # if summarization already exists, let save the planet and use the existing result csv file: 
    if twittos in summary_files_list:
        st.write("Summary already computed. Skipping GenAI summarization, here are the results: ")
          # Get the DataFrame from CSV file 
        resultsDF=pd.read_csv(twittos+'_summary.csv')
        st.dataframe(resultsDF)

    # else let's compute the summarization:    
    else: 
        object_key = twittos+'_classified.csv'  #'barackobama_classified.csv'
        print(BUCKET_NAME)
        body = cos_client.get_object(Bucket=BUCKET_NAME,Key=object_key)['Body']
        tweetDFclassified = pd.read_csv(body)

        resultsDF=resultsDF.drop(resultsDF.index)
    
        for category in categories:
            messagesCategoryDF=tweetDFclassified[tweetDFclassified['class'] == category]
            
            if messagesCategoryDF.empty:
                print("no messages in category: ", category)
            else:
                print("generating summary for category: ", category)
                
                list_tweet_group=concatenate_tweets(messagesCategoryDF,horizon=horizon_tweets)
            
                for index,list_text in enumerate(list_tweet_group):
                    prompt_input=build_prompt(list_text[0])
                    print('start date:',list_text[1],' end date:',list_text[2])
                    #if category=='Technology':
                    #print(prompt_input)
                    
                    generated_response = model.generate_text(prompt=prompt_input, guardrails=True)
                    print(generated_response)
                    new_row = {'class': category, 'summary': generated_response, 'start-date': list_text[2], 'end_date': list_text[1]}
                    resultsDF=resultsDF.append(new_row, ignore_index=True)
                    print('***********************************')

    
    # At this stage we finished the summarization, let save the result in a _summary.csv file:    
        # Save the DataFrame to a CSV file in memory
        csv_buffer = resultsDF.to_csv(index=False, sep=';')
        st.dataframe(resultsDF)
        # Upload the CSV file to IBM Cloud Object Storage
        object_key = twittos+"_summary.csv"
        cos_client.put_object(Bucket=BUCKET_NAME, Key=object_key, Body=csv_buffer)
        file_path = object_key
        import os
        if not os.path.exists(file_path): 
             with open(file_path, 'w') as file: 
                file.write(csv_buffer) 
        else: 
            print(f"The file '{file_path}' already exists. skipping task") 
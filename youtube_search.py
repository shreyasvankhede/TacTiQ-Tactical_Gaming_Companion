import os
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

youtube=build("youtube","v3",developerKey=os.getenv("YOUTUBE_API_KEY"))

def search_tutorials(keywords:str,game_name:str)->list:
    if len(keywords)!=0:
        primary=keywords
    else:
        primary=game_name + " guide tutorial"
    query= primary 
    print(f"Searching YouTube for: {query}")

    request=youtube.search().list(
        part="snippet",
        q=query,
        type="video",
        videoCategoryId="20",
        videoDefinition="high",
        maxResults=5,
        order="relevance"
    )

    response=request.execute()

    results=[]
    for item in response["items"]:
        video= {
            "title": item["snippet"]["title"],
            "channel": item["snippet"]["channelTitle"],
            "url": f"https://youtube.com/watch?v={item['id']['videoId']}",
            "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"]
        }
        results.append(video)

    return results
    
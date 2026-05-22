import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
from pymongo import MongoClient, DESCENDING, ASCENDING


load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "5000"))

if not MONGO_URI:
    raise RuntimeError("MONGO_URI is missing. Put it into .env file.")

client = MongoClient(MONGO_URI)

db_analytics = client["twitch_analytics_test2"]
db_api = client["twitch_api"]
db_chat = client["twitch_chat"]

app = Flask(__name__)
CORS(app)


def as_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def as_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def as_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "service": "Twitch MongoDB Online API",
        "databases": {
            "twitch_analytics_test2": ["streamer_stats", "top_games"],
            "twitch_api": ["hourly_game_records", "hourly_games", "hourly_streamers"],
            "twitch_chat": ["channel_stats", "raw_messages"],
        },
        "endpoints": [
            "/top_streamers",
            "/top_games",
            "/hourly_game_records",
            "/hourly_games",
            "/hourly_streamers",
            "/sentiment_over_time",
            "/messages_per_minute",
            "/top_chatters",
            "/negative_messages",
            "/channel_summary",
            "/subscribers_vs_normal",
        ]
    })


@app.route("/top_streamers")
def top_streamers():
    docs = db_analytics.streamer_stats.find(
        {},
        {"_id": 0, "user_name": 1, "game_name": 1, "peak_viewers": 1}
    ).sort("peak_viewers", DESCENDING).limit(20)

    result = [{
        "streamer": d.get("user_name", "unknown"),
        "game": d.get("game_name", "unknown"),
        "viewers": as_int(d.get("peak_viewers", 0)),
    } for d in docs]

    return jsonify(result)


@app.route("/top_games")
def top_games():
    docs = db_analytics.top_games.find(
        {},
        {"_id": 0, "game_name": 1, "total_viewers": 1, "streams_count": 1}
    ).sort("total_viewers", DESCENDING).limit(20)

    result = [{
        "game": d.get("game_name", "unknown"),
        "viewers": as_int(d.get("total_viewers", 0)),
        "streams": as_int(d.get("streams_count", 0)),
        "viewers_per_stream": round(
            as_int(d.get("total_viewers", 0)) / max(as_int(d.get("streams_count", 0)), 1),
            2
        )
    } for d in docs]

    return jsonify(result)


@app.route("/hourly_game_records")
def hourly_game_records():
    docs = db_api.hourly_game_records.find(
        {},
        {"_id": 0, "game_name": 1, "date_hour": 1, "record_viewers": 1}
    ).sort("date_hour", ASCENDING)

    result = [{
        "time": d.get("date_hour"),
        "game": d.get("game_name", "unknown"),
        "record_viewers": as_int(d.get("record_viewers", 0)),
    } for d in docs]

    return jsonify(result)


@app.route("/hourly_games")
def hourly_games():
    docs = db_api.hourly_games.find(
        {},
        {"_id": 0, "game_name": 1, "date_hour": 1, "avg_viewers": 1}
    ).sort("date_hour", ASCENDING)

    result = [{
        "time": d.get("date_hour"),
        "game": d.get("game_name", "unknown"),
        "avg_viewers": as_float(d.get("avg_viewers", 0)),
    } for d in docs]

    return jsonify(result)


@app.route("/hourly_streamers")
def hourly_streamers():
    docs = db_api.hourly_streamers.find(
        {},
        {"_id": 0, "user_name": 1, "date_hour": 1, "avg_viewers": 1}
    ).sort("date_hour", ASCENDING)

    result = [{
        "time": d.get("date_hour"),
        "streamer": d.get("user_name", "unknown"),
        "avg_viewers": as_float(d.get("avg_viewers", 0)),
    } for d in docs]

    return jsonify(result)


@app.route("/sentiment_over_time")
def sentiment_over_time():
    docs = db_chat.channel_stats.find(
        {},
        {"_id": 0, "window.start": 1, "channel": 1, "avg_sentiment": 1}
    ).sort("window.start", ASCENDING)

    result = []
    for d in docs:
        window = d.get("window", {})
        result.append({
            "time": as_iso(window.get("start")),
            "channel": d.get("channel", "unknown"),
            "avg_sentiment": as_float(d.get("avg_sentiment", 0)),
        })

    return jsonify(result)


@app.route("/messages_per_minute")
def messages_per_minute():
    pipeline = [
        {
            "$group": {
                "_id": {
                    "minute": {
                        "$dateToString": {
                            "format": "%Y-%m-%dT%H:%M:00",
                            "date": "$timestamp"
                        }
                    },
                    "channel": "$channel"
                },
                "messages": {"$sum": 1}
            }
        },
        {"$sort": {"_id.minute": 1}}
    ]

    result = []
    for d in db_chat.raw_messages.aggregate(pipeline):
        result.append({
            "time": d["_id"]["minute"],
            "channel": d["_id"].get("channel", "unknown"),
            "messages": as_int(d.get("messages", 0)),
        })

    return jsonify(result)


@app.route("/top_chatters")
def top_chatters():
    pipeline = [
        {
            "$group": {
                "_id": "$username",
                "messages": {"$sum": 1},
                "avg_sentiment": {"$avg": "$sentiment_score"}
            }
        },
        {"$sort": {"messages": -1}},
        {"$limit": 20}
    ]

    result = []
    for d in db_chat.raw_messages.aggregate(pipeline):
        result.append({
            "username": d.get("_id", "unknown"),
            "messages": as_int(d.get("messages", 0)),
            "avg_sentiment": as_float(d.get("avg_sentiment", 0)),
        })

    return jsonify(result)


@app.route("/negative_messages")
def negative_messages():
    pipeline = [
        {"$match": {"sentiment_score": {"$lt": -0.3}}},
        {
            "$group": {
                "_id": {
                    "minute": {
                        "$dateToString": {
                            "format": "%Y-%m-%dT%H:%M:00",
                            "date": "$timestamp"
                        }
                    },
                    "channel": "$channel"
                },
                "negative_messages": {"$sum": 1}
            }
        },
        {"$sort": {"_id.minute": 1}}
    ]

    result = []
    for d in db_chat.raw_messages.aggregate(pipeline):
        result.append({
            "time": d["_id"]["minute"],
            "channel": d["_id"].get("channel", "unknown"),
            "negative_messages": as_int(d.get("negative_messages", 0)),
        })

    return jsonify(result)


@app.route("/channel_summary")
def channel_summary():
    pipeline = [
        {
            "$group": {
                "_id": "$channel",
                "messages": {"$sum": 1},
                "unique_users": {"$addToSet": "$username"},
                "avg_sentiment": {"$avg": "$sentiment_score"},
                "min_sentiment": {"$min": "$sentiment_score"},
                "max_sentiment": {"$max": "$sentiment_score"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "channel": "$_id",
                "messages": 1,
                "unique_users": {"$size": "$unique_users"},
                "avg_sentiment": 1,
                "min_sentiment": 1,
                "max_sentiment": 1,
            }
        },
        {"$sort": {"messages": -1}}
    ]

    result = []
    for d in db_chat.raw_messages.aggregate(pipeline):
        result.append({
            "channel": d.get("channel", "unknown"),
            "messages": as_int(d.get("messages", 0)),
            "unique_users": as_int(d.get("unique_users", 0)),
            "avg_sentiment": as_float(d.get("avg_sentiment", 0)),
            "min_sentiment": as_float(d.get("min_sentiment", 0)),
            "max_sentiment": as_float(d.get("max_sentiment", 0)),
        })

    return jsonify(result)


@app.route("/subscribers_vs_normal")
def subscribers_vs_normal():
    pipeline = [
        {
            "$project": {
                "sentiment_score": 1,
                "user_type": {
                    "$cond": [
                        {"$ne": ["$badges.subscriber", None]},
                        "subscriber",
                        "normal_user"
                    ]
                }
            }
        },
        {
            "$group": {
                "_id": "$user_type",
                "messages": {"$sum": 1},
                "avg_sentiment": {"$avg": "$sentiment_score"}
            }
        }
    ]

    result = []
    for d in db_chat.raw_messages.aggregate(pipeline):
        result.append({
            "user_type": d.get("_id", "unknown"),
            "messages": as_int(d.get("messages", 0)),
            "avg_sentiment": as_float(d.get("avg_sentiment", 0)),
        })

    return jsonify(result)


if __name__ == "__main__":
    app.run(host=API_HOST, port=API_PORT, debug=False)

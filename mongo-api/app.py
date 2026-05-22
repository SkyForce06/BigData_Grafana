from flask import Flask, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)

db_api = client["twitch_api"]
db_chat = client["twitch_chat"]
db_analytics = client["twitch_analytics_test2"]


def to_iso(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


@app.route("/")
def home():
    return jsonify({
        "status": "API works",
        "endpoints": [
            "/top_streamers",
            "/top_games",
            "/top_games_efficiency",
            "/hourly_games",
            "/hourly_game_records",
            "/hourly_streamers",
            "/sentiment_over_time",
            "/messages_per_minute",
            "/top_chatters",
            "/channel_summary",
            "/negative_messages",
            "/subscribers_vs_normal"
        ]
    })


@app.route("/top_streamers")
def top_streamers():
    data = list(db_analytics.streamer_stats.find(
        {},
        {"_id": 0, "user_name": 1, "game_name": 1, "peak_viewers": 1}
    ).sort("peak_viewers", -1).limit(20))

    return jsonify([
        {
            "streamer": d.get("user_name"),
            "game": d.get("game_name"),
            "viewers": int(d.get("peak_viewers", 0))
        }
        for d in data
    ])


@app.route("/top_games")
def top_games():
    data = list(db_analytics.top_games.find(
        {},
        {"_id": 0, "game_name": 1, "total_viewers": 1, "streams_count": 1}
    ).sort("total_viewers", -1).limit(20))

    return jsonify([
        {
            "game": d.get("game_name"),
            "viewers": int(d.get("total_viewers", 0)),
            "streams": int(d.get("streams_count", 0))
        }
        for d in data
    ])


@app.route("/top_games_efficiency")
def top_games_efficiency():
    data = list(db_analytics.top_games.find(
        {},
        {"_id": 0, "game_name": 1, "total_viewers": 1, "streams_count": 1}
    ))

    result = []

    for d in data:
        viewers = int(d.get("total_viewers", 0))
        streams = int(d.get("streams_count", 0))

        if streams > 0:
            result.append({
                "game": d.get("game_name"),
                "viewers_per_stream": round(viewers / streams, 2),
                "total_viewers": viewers,
                "streams": streams
            })

    result.sort(key=lambda x: x["viewers_per_stream"], reverse=True)

    return jsonify(result[:20])


@app.route("/hourly_games")
def hourly_games():
    data = list(db_api.hourly_games.find(
        {},
        {"_id": 0, "game_name": 1, "date_hour": 1, "avg_viewers": 1}
    ).sort("date_hour", 1))

    return jsonify([
        {
            "time": d.get("date_hour"),
            "game": d.get("game_name"),
            "avg_viewers": float(d.get("avg_viewers", 0))
        }
        for d in data
    ])


@app.route("/hourly_game_records")
def hourly_game_records():
    data = list(db_api.hourly_game_records.find(
        {},
        {"_id": 0, "game_name": 1, "date_hour": 1, "record_viewers": 1}
    ).sort("date_hour", 1))

    return jsonify([
        {
            "time": d.get("date_hour"),
            "game": d.get("game_name"),
            "record_viewers": int(d.get("record_viewers", 0))
        }
        for d in data
    ])


@app.route("/hourly_streamers")
def hourly_streamers():
    data = list(db_api.hourly_streamers.find(
        {},
        {"_id": 0, "user_name": 1, "date_hour": 1, "avg_viewers": 1}
    ).sort("date_hour", 1))

    return jsonify([
        {
            "time": d.get("date_hour"),
            "streamer": d.get("user_name"),
            "avg_viewers": float(d.get("avg_viewers", 0))
        }
        for d in data
    ])


@app.route("/sentiment_over_time")
def sentiment_over_time():
    data = list(db_chat.channel_stats.find(
        {},
        {"_id": 0, "window.start": 1, "channel": 1, "avg_sentiment": 1}
    ).sort("window.start", 1))

    return jsonify([
        {
            "time": to_iso(d["window"]["start"]),
            "channel": d.get("channel"),
            "avg_sentiment": float(d.get("avg_sentiment", 0))
        }
        for d in data
    ])


@app.route("/messages_per_minute")
def messages_per_minute():
    data = list(db_chat.raw_messages.aggregate([
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
    ]))

    return jsonify([
        {
            "time": d["_id"]["minute"],
            "channel": d["_id"]["channel"],
            "messages": int(d["messages"])
        }
        for d in data
    ])


@app.route("/top_chatters")
def top_chatters():
    data = list(db_chat.raw_messages.aggregate([
        {
            "$group": {
                "_id": "$username",
                "messages": {"$sum": 1}
            }
        },
        {"$sort": {"messages": -1}},
        {"$limit": 20}
    ]))

    return jsonify([
        {
            "username": d["_id"],
            "messages": int(d["messages"])
        }
        for d in data
    ])


@app.route("/channel_summary")
def channel_summary():
    data = list(db_chat.raw_messages.aggregate([
        {
            "$group": {
                "_id": "$channel",
                "messages": {"$sum": 1},
                "unique_users": {"$addToSet": "$username"},
                "avg_sentiment": {"$avg": "$sentiment_score"}
            }
        },
        {
            "$project": {
                "_id": 0,
                "channel": "$_id",
                "messages": 1,
                "unique_users": {"$size": "$unique_users"},
                "avg_sentiment": 1
            }
        },
        {"$sort": {"messages": -1}}
    ]))

    return jsonify([
        {
            "channel": d["channel"],
            "messages": int(d["messages"]),
            "unique_users": int(d["unique_users"]),
            "avg_sentiment": round(float(d.get("avg_sentiment", 0)), 4)
        }
        for d in data
    ])


@app.route("/negative_messages")
def negative_messages():
    data = list(db_chat.raw_messages.aggregate([
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
    ]))

    return jsonify([
        {
            "time": d["_id"]["minute"],
            "channel": d["_id"]["channel"],
            "negative_messages": int(d["negative_messages"])
        }
        for d in data
    ])


@app.route("/subscribers_vs_normal")
def subscribers_vs_normal():
    data = list(db_chat.raw_messages.aggregate([
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
    ]))

    return jsonify([
        {
            "user_type": d["_id"],
            "messages": int(d["messages"]),
            "avg_sentiment": round(float(d.get("avg_sentiment", 0)), 4)
        }
        for d in data
    ])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

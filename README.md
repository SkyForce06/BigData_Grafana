# Twitch Grafana MongoDB Online API

Architecture:

```text
MongoDB Atlas -> Python API -> Grafana Infinity
```

No JSON files are saved locally. Grafana reads online data from the API, and the API reads MongoDB Atlas.

## 1. Prepare `.env`

Copy:

```bash
copy .env.example .env
```

or on Linux/macOS:

```bash
cp env.example .env
```

Then put your MongoDB Atlas URI into `.env`.

## 2. Start

```bash
docker compose up -d --build
```

## 3. Open

Grafana:

```text
http://localhost:3000
```

Login:

```text
admin
admin
```

API health check:

```text
http://localhost:5000/
```

## 4. API endpoints

```text
/top_streamers
/top_games
/hourly_game_records
/hourly_games
/hourly_streamers
/sentiment_over_time
/messages_per_minute
/top_chatters
/negative_messages
/channel_summary
/subscribers_vs_normal
```

Inside Grafana Docker use this base URL:

```text
http://mongo-api:5000
```

For browser testing use:

```text
http://localhost:5000
```

## 5. Grafana Infinity datasource

Install should happen automatically through Docker env.

In Grafana:

```text
Connections -> Data sources -> Add data source -> Infinity
```

Base URL:

```text
http://mongo-api:5000
```

Allowed hosts / security:

```text
mongo-api:5000
```


# PriceWatch — Real-Time Price Monitoring System

A production-grade, fully serverless price monitoring platform built on AWS. Automatically tracks product prices across major retailers, detects price changes, and delivers real-time alerts — all without managing a single server.

**Live Dashboard:** http://pricewatch-dashboard.s3-website.us-east-2.amazonaws.com

---

## Architecture
EventBridge (every 30 min)
└── Lambda Scraper (Docker + curl_cffi)
├── DynamoDB        — price storage & history
├── SNS             — email alerts on threshold breach
└── S3              — structured execution logs (JSON)

User Request
└── API Gateway (REST)
└── Lambda API (Docker + boto3)
└── DynamoDB
  Static Dashboard (S3 + public hosting)
└── API Gateway → Lambda API → DynamoDB

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Compute | AWS Lambda (Docker/ECR) |
| Storage | Amazon DynamoDB |
| API | Amazon API Gateway (REST) |
| Scheduling | Amazon EventBridge |
| Alerts | Amazon SNS |
| Hosting | Amazon S3 (static website) |
| Logs | Amazon S3 (JSON) |
| Scraping | Python, curl_cffi, BeautifulSoup |
| Frontend | Vanilla JS, CSS3, Chart.js |

## Key Features

- **Automatic price tracking** — EventBridge triggers the scraper every 30 minutes across all monitored products
- **Smart scraping** — uses `curl_cffi` with Chrome impersonation to bypass bot detection; Mercado Libre is queried via its official API
- **Price history** — every price change is recorded in DynamoDB with timestamp, enabling full trend visualization
- **Threshold alerts** — SNS sends email notifications when a product's price change exceeds the user-defined percentage threshold
- **REST API** — full CRUD API built on Lambda + API Gateway with CORS support
- **Interactive dashboard** — real-time charts, store filtering, add/edit/delete products, URL validation with automatic price extraction
- **Execution logs** — every scraper run produces a structured JSON log stored in S3

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/products` | List all monitored products |
| `POST` | `/products` | Add a new product |
| `DELETE` | `/products/{id}` | Remove a product |
| `PATCH` | `/products/{id}` | Update name, threshold, or image |
| `GET` | `/products/{id}/history` | Full price history for a product |
| `POST` | `/check-url` | Validate URL and extract current price |

## Project Structure
/scraper        Price extraction Lambda — Docker image deployed to ECR
/api            REST API Lambda — Docker image deployed to ECR
/dashboard      Static frontend — HTML, CSS, Vanilla JS

## Tested supported Retailers

| Retailer | Method |
|----------|--------|
| Amazon MX | HTML scraping (curl_cffi + Chrome impersonation) |
| Mercado Libre MX | Official REST API |
| Farmacias Guadalajara | HTML scraping |
| BuscaLibre MX | HTML scraping |
| Nike MX | HTML scraping |
| Books to Scrape | HTML scraping |

## Team

| Member | Responsibilities |
|--------|----------------|
| Stephanie Borrego | DynamoDB design, Lambda API, API Gateway, S3 dashboard, Lambda Scraper |
| Alejandra | Lambda Scraper, S3 execution logs |
| Hannah Chenoa | EventBridge scheduling, SNS alerts, end-to-end integration |

## Known Limitations & Future Work

- **Authentication** — currently single-tenant; multi-user support planned via Amazon Cognito
- **Image loading** — Some product images blocked by CORS; added manually or via Google Images
- **Retailer coverage** — Liverpool and Walmart actively block scraping; proxy rotation or browser automation (Playwright) would be required

---

*Built for Cloud Computing Course— ITESO *

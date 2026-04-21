# PriceWatch 🔍

Sistema serverless de monitoreo de precios en tiempo real, construido sobre AWS como proyecto final del Diplomado Cloud Computing — ITESO / Intel Partnership 2026.

## Arquitectura
EventBridge (cron 30min)
→ Lambda Scraper → DynamoDB
→ SNS (alertas por email)
→ S3 (logs JSON)
Usuario → API Gateway → Lambda API → DynamoDB
Dashboard (S3 static hosting) → API Gateway

## Servicios AWS utilizados

- **DynamoDB** — almacenamiento de productos e historial de precios
- **Lambda** — scraper de precios y API REST
- **API Gateway** — exposición pública de endpoints REST
- **EventBridge** — ejecución automática del scraper cada 30 minutos
- **SNS** — alertas por email cuando un precio supera el umbral configurado
- **S3** — hosting del dashboard y almacenamiento de logs
- **ECR** — registro de imágenes Docker para las funciones Lambda

## Estructura del proyecto
/scraper      Lambda que extrae precios de tiendas en línea
/api          Lambda que expone los datos via REST
/dashboard    Frontend estático (HTML, CSS, JS)

## Tiendas soportadas

- Amazon MX
- Mercado Libre MX (via API oficial)
- Farmacias Guadalajara
- BuscaLibre MX
- Nike MX
- Books to Scrape

## Dashboard

URL pública: http://pricewatch-dashboard.s3-website.us-east-2.amazonaws.com

Funcionalidades:
- Visualización de productos con imagen, precio actual y variación
- Gráfica de historial de precios por producto
- Filtros por tienda y estado (bajó / subió / sin cambio)
- Agregar, editar y eliminar productos
- Verificación automática de URL y extracción de precio
- Notificaciones del navegador cuando un precio cambia

## API Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | /products | Lista todos los productos |
| POST | /products | Agrega un producto nuevo |
| DELETE | /products/{id} | Elimina un producto |
| PATCH | /products/{id} | Edita nombre, umbral o imagen |
| GET | /products/{id}/history | Historial de precios |
| POST | /check-url | Verifica si una URL es scrapeable |

## Equipo

- **Stephanie Borrego** — DynamoDB, Lambda API, API Gateway, Dashboard
- **Alejandra** — Lambda Scraper, Logs en S3
- **Hannah Chenoa** — EventBridge, SNS, Integración end-to-end

## Limitaciones conocidas

- Amazon bloquea imágenes via CORS — se agregan manualmente
- Liverpool y Walmart bloquean scraping completamente
- Sin autenticación de usuarios — mejora futura con Amazon Cognito

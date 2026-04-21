import json
import os
import time
import random
import boto3
import re
from datetime import datetime
from bs4 import BeautifulSoup
from curl_cffi import requests
from urllib.parse import urlparse
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.client("dynamodb", region_name="us-east-2")
sns      = boto3.client("sns",      region_name="us-east-2")
s3       = boto3.client("s3",       region_name="us-east-2")
domain_last_request = {}
RATE_LIMIT_SECONDS = 3

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

def get_random_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-MX,es;q=0.8,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

def respect_rate_limit(domain):
    now = time.time()
    if domain in domain_last_request:
        elapsed = now - domain_last_request[domain]
        if elapsed < RATE_LIMIT_SECONDS:
            time.sleep(RATE_LIMIT_SECONDS - elapsed)
    domain_last_request[domain] = time.time()

def human_delay(min_sec=1, max_sec=3):
    time.sleep(random.uniform(min_sec, max_sec))

def get_products_from_dynamodb():
    productos = []
    kwargs = {"TableName": "Products"}
    try:
        while True:
            response = dynamodb.scan(**kwargs)
            for item in response["Items"]:
                productos.append({
                    "productId": item["productId"]["S"],
                    "nombre":    item["name"]["S"],
                    "url":       item["url"]["S"],
                    "alertThreshold": float(item["alertThreshold"]["N"]),
                    "currentPrice":   float(item["currentPrice"]["N"])
                })
            if "LastEvaluatedKey" not in response:
                break
            kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    except Exception as e:
        print(f"Error leyendo Products: {str(e)}")
    return productos

def save_to_price_history(product_id, precio_nuevo, precio_anterior, variacion):
    try:
        timestamp = datetime.utcnow().isoformat()
        dynamodb.put_item(
            TableName="PriceHistory",
            Item={
                "productId": {"S": product_id},
                "timestamp": {"S": timestamp},
                "price": {"N": str(precio_nuevo)},
                "previousPrice": {"N": str(precio_anterior)},
                "priceChange": {"N": str(round(variacion, 2))}
            }
        )
        print(f"Guardado en PriceHistory: {product_id} → ${precio_nuevo}")
    except Exception as e:
        print(f"Error guardando: {str(e)}")

def send_alert(product_name, precio_anterior, precio_nuevo, variacion, url):
    try:
        topic_arn = os.environ["SNS_TOPIC_ARN"]
        direccion = "bajó" if variacion < 0 else "subió"
        mensaje = f"""
PriceWatch — Alerta de precio

Producto: {product_name}
Precio anterior: ${precio_anterior:,.2f}
Precio actual: ${precio_nuevo:,.2f}
Variación: {variacion:+.1f}%
El precio {direccion} más del umbral configurado.

Ver producto: {url}
        """
        sns.publish(
            TopicArn=topic_arn,
            Subject=f"{'📉' if variacion < 0 else '📈'} {product_name} — variación de {abs(variacion):.1f}%",
            Message=mensaje
        )
        print(f"Alerta SNS enviada: {product_name}")
    except Exception as e:
        print(f"Error enviando alerta SNS: {str(e)}")

def update_current_price(product_id, precio_nuevo):
    try:
        dynamodb.update_item(
            TableName="Products",
            Key={"productId": {"S": product_id}},
            UpdateExpression="SET currentPrice = :precio",
            ExpressionAttributeValues={":precio": {"N": str(precio_nuevo)}}
        )
        print(f"currentPrice actualizado: {product_id} → ${precio_nuevo}")
    except Exception as e:
        print(f"Error actualizando currentPrice: {str(e)}")

def calcular_variacion(precio_anterior, precio_nuevo):
    if precio_anterior == 0: return 0
    return ((precio_nuevo - precio_anterior) / precio_anterior) * 100

def extract_price(text):
    if not text: return None
    text = text.strip().replace(',', '').replace('$', '').replace('MXN', '').replace('USD', '')
    patterns = [r'(\d+\.\d{2})', r'(\d+\.\d{1})', r'(\d+)']
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                price = float(match.group(1))
                if 1 < price < 100000: return price
            except: pass
    return None

def scrape_mercadolibre_api(url):
    match = re.search(r'(MLM\-?\d+)', url, re.IGNORECASE)
    if not match:
        return None, ""
    item_id = match.group(1).replace('-', '').upper()
    api_url = f"https://api.mercadolibre.com/items/{item_id}"
    try:
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return float(data.get('price')), ""
    except Exception as e:
        print(f"Error en API de ML: {e}")
    return None, ""

def scrape_books_toscrape(soup, url):
    price = soup.select_one('.price_color')
    if price: return extract_price(price.text)
    return None

def scrape_amazon(soup, url):
    selectors = [
        'span.a-price-whole',
        '.a-price .a-offscreen',
        '#priceblock_ourprice',
        '#priceblock_dealprice',
        '#corePriceDisplay_desktop_feature_div .a-price .a-offscreen'
    ]
    for selector in selectors:
        try:
            element = soup.select_one(selector)
            if element:
                raw_text = element.text.strip().replace(',', '').replace('$', '').replace('\xa0', '')
                if 'a-price-whole' in selector:
                    fraction = soup.select_one('span.a-price-fraction')
                    if fraction:
                        return float(f"{raw_text.split('.')[0]}.{fraction.text.strip()}")
                price = extract_price(raw_text)
                if price: return price
        except:
            logger.warning("amazon_selector_failed", extra={"selector": selector, "error": str(e)})
    try:
        twister = soup.select_one('#twister-plus-inline-twister-card')
        if twister:
            price_match = re.search(r'"priceAmount":(\d+\.\d+)', str(twister))
            if price_match:
                return float(price_match.group(1))
    except:
        pass
    return extract_price(soup.get_text())

def scrape_zara(soup, url):
    try:
        scripts = soup.find_all("script")
        for script in scripts:
            if script.string and "price" in script.string.lower():
                match = re.search(r'"price"\s*:\s*(\d+\.?\d*)', script.string)
                if match:
                    price = float(match.group(1))
                    if price > 10000:
                        price = price / 100
                    return price
    except:
        pass
    meta = soup.select_one('meta[property="product:price:amount"]')
    if meta and meta.get("content"):
        return extract_price(meta.get("content"))
    return None

def scrape_generic(soup, url):
    meta_selectors = ['meta[property="product:price:amount"]', 'meta[itemprop="price"]']
    for selector in meta_selectors:
        element = soup.select_one(selector)
        if element and element.get('content'): return extract_price(element.get('content'))
    class_patterns = ['price', 'precio', 'product-price']
    for pattern in class_patterns:
        elements = soup.find_all(class_=re.compile(pattern, re.I))
        for element in elements:
            price = extract_price(element.text.strip())
            if price: return price
    return extract_price(soup.get_text())

def get_scraper_function(domain):
    domain_map = {
        'books.toscrape.com': scrape_books_toscrape,
        'amazon.com': scrape_amazon,
        'amazon.com.mx': scrape_amazon,
        'a.co': scrape_amazon,
        'zara.com': scrape_zara,
    }
    for key, func in domain_map.items():
        if key in domain: return func
    return scrape_generic

def scrape_url(url):
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        print(f"Scrapeando: {domain}")
        if 'mercadolibre.com' in domain:
            precio_api, _ = scrape_mercadolibre_api(url)
            if precio_api:
                print(f"Precio encontrado vía API ML: ${precio_api}")
                return precio_api, ""
        respect_rate_limit(domain)
        response = requests.get(
            url,
            headers=get_random_headers(),
            impersonate="chrome124",
            timeout=30,
            verify=False
        )
        if response.status_code != 200:
            print(f"Error HTTP {response.status_code}")
            return None, ""
        page_text = response.text.lower()
        if any(keyword in page_text for keyword in ['access denied', 'verifica tu identidad', 'captcha']):
            print("Bloqueado por el servidor.")
            return None, ""
        soup = BeautifulSoup(response.text, "html.parser")

        og_image = ""
        try:
            meta_img = soup.find("meta", {"property": "og:image"})
            if meta_img and meta_img.get("content"):
                og_image = meta_img["content"]
        except:
            pass

        scraper_func = get_scraper_function(domain)
        price = scraper_func(soup, url)
        if price:
            print(f"Precio encontrado: ${price}")
            return price, og_image
        return None, og_image

    except Exception as e:
        logger.error("scrape_url_failed", extra={"url": url, "error": str(e)})
        return None, ""

def lambda_handler(event, context):
    print("Iniciando scraper...")
    productos = get_products_from_dynamodb()
    if not productos: return {"statusCode": 200, "body": json.dumps({"mensaje": "No hay productos"})}
    resultados = []
    for producto in productos:
        print(f"\nProcesando: {producto['nombre']}")
        precio_nuevo, og_image = scrape_url(producto["url"])
        precio_anterior = producto["currentPrice"]
        if precio_nuevo is None:
            resultados.append({"productId": producto["productId"], "nombre": producto["nombre"], "status": "error_scraping"})
            continue
        if precio_anterior > 0 and precio_nuevo < precio_anterior * 0.5:
            resultados.append({"productId": producto["productId"], "nombre": producto["nombre"], "status": "precio_sospechoso"})
            continue
        if precio_nuevo == precio_anterior:
            resultados.append({"productId": producto["productId"], "nombre": producto["nombre"], "precioActual": precio_nuevo, "status": "sin_cambio"})
            continue
        variacion = calcular_variacion(precio_anterior, precio_nuevo)
        save_to_price_history(producto["productId"], precio_nuevo, precio_anterior, variacion)
        update_current_price(producto["productId"], precio_nuevo)
        if abs(variacion) >= producto["alertThreshold"]:
            send_alert(producto["nombre"], precio_anterior, precio_nuevo, variacion, producto.get("url", ""))
        if og_image:
            try:
                dynamodb.update_item(
                    TableName="Products",
                    Key={"productId": {"S": producto["productId"]}},
                    UpdateExpression="SET image = :img",
                    ExpressionAttributeValues={":img": {"S": og_image}}
                )
            except:
                pass
        resultados.append({
            "productId": producto["productId"],
            "nombre": producto["nombre"],
            "precioAnterior": precio_anterior,
            "precioNuevo": precio_nuevo,
            "variacion": round(variacion, 2),
            "status": "ok"
        })
        human_delay(1, 3)

    # Guardar log en S3 al finalizar todos los productos
    try:
        timestamp = datetime.utcnow().strftime("%Y/%m/%d")
        run_id    = datetime.utcnow().strftime("%H-%M-%S")
        log = {
            "timestamp": datetime.utcnow().isoformat(),
            "total": len(resultados),
            "ok": len([r for r in resultados if r.get("status") == "ok"]),
            "errores": len([r for r in resultados if "error" in r.get("status", "")]),
            "resultados": resultados
        }
        s3.put_object(
            Bucket=os.environ["S3_LOGS_BUCKET"],
            Key=f"logs/{timestamp}/run-{run_id}.json",
            Body=json.dumps(log, ensure_ascii=False),
            ContentType="application/json"
        )
        print("Log guardado en S3")
    except Exception as e:
        print(f"Error guardando log: {str(e)}")

    return {"statusCode": 200, "body": json.dumps(resultados)}
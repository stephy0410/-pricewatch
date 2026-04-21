import json
import boto3
import urllib.request
from boto3.dynamodb.conditions import Key
from decimal import Decimal

dynamodb = boto3.resource("dynamodb", region_name="us-east-2")
products_table = dynamodb.Table("Products")
history_table = dynamodb.Table("PriceHistory")

def decimal_to_float(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def cors_headers():
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }

def get_products(event, context):
    try:
        response = products_table.scan()
        return {
            "statusCode": 200,
            "headers": cors_headers(),
            "body": json.dumps(response["Items"], default=decimal_to_float)
        }
    except Exception as e:
        return {"statusCode": 500, "headers": cors_headers(), "body": json.dumps({"error": str(e)})}

def get_product_history(event, context):
    try:
        product_id = event["pathParameters"]["productId"]
        response = history_table.query(
            KeyConditionExpression=Key("productId").eq(product_id),
            ScanIndexForward=False,
            Limit=100
        )
        return {
            "statusCode": 200,
            "headers": cors_headers(),
            "body": json.dumps(response["Items"], default=decimal_to_float)
        }
    except Exception as e:
        return {"statusCode": 500, "headers": cors_headers(), "body": json.dumps({"error": str(e)})}

def check_url(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        url = body.get("url", "").strip()
        if not url:
            return {"statusCode": 400, "headers": cors_headers(), "body": json.dumps({"error": "URL requerida"})}

        import re
        from curl_cffi import requests as cffi_requests
        from bs4 import BeautifulSoup

        try:
            response = cffi_requests.get(
                url,
                impersonate="chrome124",
                timeout=10,
                verify=False
            )
            html   = response.text
            status = response.status_code
            if status != 200:
                raise Exception(f"HTTP {status}")
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            return {
                "statusCode": 200,
                "headers": cors_headers(),
                "body": json.dumps({
                    "scrapeable": False,
                    "price": None,
                    "og_image": "",
                    "og_title": "",
                    "store": "",
                    "message": f"URL no accesible — intenta con otro link o tienda."
                })
            }

        og_image = ""
        og_title = ""
        store    = ""

        try:
            meta_img   = soup.find("meta", {"property": "og:image"})
            meta_title = soup.find("meta", {"property": "og:title"})
            meta_site  = soup.find("meta", {"property": "og:site_name"})
            if meta_img   and meta_img.get("content"):   og_image = meta_img["content"]
            if meta_title and meta_title.get("content"): og_title = meta_title["content"]
            if meta_site  and meta_site.get("content"):  store    = meta_site["content"]
        except:
            pass

        if not store:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            if "amazon"      in domain: store = "Amazon MX"
            elif "mercadolibre" in domain: store = "Mercado Libre MX"
            elif "walmart"   in domain: store = "Walmart MX"
            elif "liverpool" in domain: store = "Liverpool"
            elif "buscalibre" in domain: store = "BuscaLibre MX"
            elif "nike"      in domain: store = "Nike MX"
            elif "farmacias" in domain: store = "Farmacias Guadalajara"
            elif "a.co" in domain: store = "Amazon MX"
            else: store = domain.replace("www.", "").split(".")[0].capitalize()

        price = None

        try:
            meta_price = soup.find("meta", {"property": "product:price:amount"})
            if meta_price and meta_price.get("content"):
                price = float(meta_price["content"].replace(",", ""))
        except:
            pass

        if not price:
            for script in soup.find_all("script", {"type": "application/ld+json"}):
                try:
                    import json as _json
                    data = _json.loads(script.string)
                    if isinstance(data, list): data = data[0]
                    offers = data.get("offers", {})
                    if isinstance(offers, list): offers = offers[0]
                    p = offers.get("price")
                    if p:
                        price = float(str(p).replace(",", ""))
                        break
                except:
                    pass

        if not price:
            patterns = [
                r'"price"\s*:\s*"?([\d,]+\.?\d*)"?',
                r'"priceAmount"\s*:\s*([\d.]+)',
                r"'price'\s*:\s*([\d.]+)",
                r'itemprop=["\']price["\'][^>]+content=["\']([^"\']+)["\']',
            ]
            for pat in patterns:
                m = re.search(pat, html)
                if m:
                    try:
                        candidate = float(m.group(1).replace(",", ""))
                        if 1 < candidate < 500000:
                            price = candidate
                            break
                    except:
                        pass

        if not price:
            try:
                price_tag = soup.select_one("span.a-price-whole")
                fraction  = soup.select_one("span.a-price-fraction")
                if price_tag:
                    raw = price_tag.text.strip().replace(",", "").replace(".", "")
                    frac = fraction.text.strip() if fraction else "00"
                    price = float(f"{raw}.{frac}")
            except:
                pass

        scrapeable = price is not None

        return {
            "statusCode": 200,
            "headers": cors_headers(),
            "body": json.dumps({
                "scrapeable": scrapeable,
                "price": price,
                "og_image": og_image,
                "og_title": og_title,
                "store": store,
                "message": f"Precio detectado: ${price:,.2f}" if scrapeable else "No se detectó precio automáticamente — ingresa los datos manualmente."
            })
        }
    except Exception as e:
        return {"statusCode": 500, "headers": cors_headers(), "body": json.dumps({"error": str(e)})}
def add_product(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        required = ["productId", "name", "url", "store", "currentPrice", "alertThreshold"]
        for field in required:
            if field not in body:
                return {"statusCode": 400, "headers": cors_headers(), "body": json.dumps({"error": f"Campo requerido: {field}"})}

        item = {
            "productId": body["productId"],
            "name": body["name"],
            "url": body["url"],
            "store": body["store"],
            "currentPrice": Decimal(str(body["currentPrice"])),
            "initialPrice": Decimal(str(body["currentPrice"])),
            "alertThreshold": Decimal(str(body["alertThreshold"])),
        }
        if body.get("image"): item["image"] = body["image"]

        products_table.put_item(Item=item)
        return {
            "statusCode": 201,
            "headers": cors_headers(),
            "body": json.dumps({"message": "Producto agregado", "productId": body["productId"]})
        }
    except Exception as e:
        return {"statusCode": 500, "headers": cors_headers(), "body": json.dumps({"error": str(e)})}

def delete_product(event, context):
    try:
        product_id = event["pathParameters"]["productId"]
        products_table.delete_item(
            Key={"productId": product_id}
        )
        return {
            "statusCode": 200,
            "headers": cors_headers(),
            "body": json.dumps({"message": "Producto eliminado"})
        }
    except Exception as e:
        return {"statusCode": 500, "headers": cors_headers(), "body": json.dumps({"error": str(e)})}

def patch_product(event, context):
    try:
        product_id = event["pathParameters"]["productId"]
        body = json.loads(event.get("body", "{}"))
        
        updates = []
        values  = {}
        
        if "name" in body:
            updates.append("#n = :name")
            values[":name"] = body["name"]
        if "alertThreshold" in body:
            updates.append("alertThreshold = :thr")
            values[":thr"] = Decimal(str(body["alertThreshold"]))
        if "image" in body:
            updates.append("image = :img")
            values[":img"] = body["image"]
        
        if not updates:
            return {"statusCode": 400, "headers": cors_headers(), "body": json.dumps({"error": "Nada que actualizar"})}
        
        kwargs = {
            "Key": {"productId": product_id},
            "UpdateExpression": "SET " + ", ".join(updates),
            "ExpressionAttributeValues": values
        }
        if "#n" in " ".join(updates):
            kwargs["ExpressionAttributeNames"] = {"#n": "name"}
        
        products_table.update_item(**kwargs)
        return {"statusCode": 200, "headers": cors_headers(), "body": json.dumps({"message": "Actualizado"})}
    except Exception as e:
        return {"statusCode": 500, "headers": cors_headers(), "body": json.dumps({"error": str(e)})}

def lambda_handler(event, context):
    method = event.get("httpMethod", "GET")
    path = event.get("path", "")

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": cors_headers(), "body": ""}

    if method == "GET" and path == "/products":
        return get_products(event, context)
    elif method == "GET" and "/products/" in path and "/history" in path:
        return get_product_history(event, context)
    elif method == "POST" and path == "/products":
        return add_product(event, context)
    elif method == "POST" and path == "/check-url":
        return check_url(event, context)
    elif method == "DELETE" and "/products/" in path:
        return delete_product(event, context)
    elif method == "PATCH" and "/products/" in path:
        return patch_product(event, context)
    else:
        return {"statusCode": 404, "headers": cors_headers(), "body": json.dumps({"error": "Ruta no encontrada"})}
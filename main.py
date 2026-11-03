import time
from datetime import datetime
import httpx
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

cache = {"time": 0, "data": None}


async def get_cbr_data():
    now = time.time()
    if cache["data"] and (now - cache["time"] < 60):
        return cache["data"]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://www.cbr-xml-daily.ru/daily_json.js")
            if resp.status_code == 200:
                cache["data"] = resp.json()
                cache["time"] = now
    except Exception:
        pass

    return cache["data"]


@app.get("/")
async def index(request: Request):
    data = await get_cbr_data()
    if not data:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "date_str": "",
                "timestamp_str": "",
                "usd": {"value": "0", "arrow": ""},
                "eur": {"value": "0", "arrow": ""},
                "valutes": []
            }
        )

    try:
        date_str = datetime.fromisoformat(data.get("Date", "")).strftime("%d.%m.%Y")
    except Exception:
        date_str = ""

    try:
        timestamp_str = datetime.fromisoformat(data.get("Timestamp", "")).strftime("%d.%m.%Y, %H:%M:%S")
    except Exception:
        timestamp_str = ""

    valutes = data.get("Valute", {})

    usd_data = valutes.get("USD", {})
    usd_val = usd_data.get("Value", 0.0)
    usd_diff = usd_val - usd_data.get("Previous", usd_val)
    usd_arrow = "▲" if usd_diff > 0 else ("▼" if usd_diff < 0 else "")

    eur_data = valutes.get("EUR", {})
    eur_val = eur_data.get("Value", 0.0)
    eur_diff = eur_val - eur_data.get("Previous", eur_val)
    eur_arrow = "▲" if eur_diff > 0 else ("▼" if eur_diff < 0 else "")

    valutes_list = []
    for code, item in valutes.items():
        val = item.get("Value", 0.0)
        prev = item.get("Previous", val)
        diff = val - prev
        sign = "+" if diff > 0 else ""

        valutes_list.append({
            "NumCode": item.get("NumCode", ""),
            "CharCode": item.get("CharCode", code),
            "Nominal": item.get("Nominal", 1),
            "Name": item.get("Name", ""),
            "ValueFormatted": f"{val:.4f}".replace(".", ","),
            "ChangeFormatted": f"{sign}{diff:.1f}".replace(".", ",")
        })

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "date_str": date_str,
            "timestamp_str": timestamp_str,
            "usd": {
                "value": f"{usd_val:.4f}".replace(".", ","),
                "arrow": usd_arrow
            },
            "eur": {
                "value": f"{eur_val:.4f}".replace(".", ","),
                "arrow": eur_arrow
            },
            "valutes": valutes_list
        }
    )


@app.get("/currency/{char_code}")
async def currency_detail(request: Request, char_code: str, amount: float = 1.0):
    data = await get_cbr_data()
    valutes = data.get("Valute", {}) if data else {}
    char_code = char_code.upper()

    if char_code not in valutes:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"date_str": "", "timestamp_str": "", "usd": {}, "eur": {}, "valutes": []}
        )

    item = valutes[char_code]
    nominal = item.get("Nominal", 1)
    val = item.get("Value", 0.0)
    prev = item.get("Previous", val)
    diff = val - prev
    sign = "+" if diff > 0 else ""

    usd_rate = valutes.get("USD", {}).get("Value", 1.0)
    eur_rate = valutes.get("EUR", {}).get("Value", 1.0)

    rate_one = val / nominal if nominal else val
    price_usd = rate_one / usd_rate if usd_rate else 0.0
    price_eur = rate_one / eur_rate if eur_rate else 0.0

    if amount < 0:
        amount = 1.0

    total_rub = round(amount * rate_one, 2)
    total_usd = round(amount * price_usd, 2)
    total_eur = round(amount * price_eur, 2)

    valute_info = {
        "Name": item.get("Name", ""),
        "CharCode": item.get("CharCode", char_code),
        "NumCode": item.get("NumCode", ""),
        "Nominal": nominal,
        "ValueFormatted": f"{val:.4f}".replace(".", ","),
        "PreviousFormatted": f"{prev:.4f}".replace(".", ","),
        "DiffFormatted": f"{sign}{diff:.4f}".replace(".", ","),
        "PriceUsd": f"{price_usd:,.4f}".replace(",", " "),
        "PriceEur": f"{price_eur:,.4f}".replace(",", " ")
    }

    return templates.TemplateResponse(
        request=request,
        name="currency.html",
        context={
            "valute": valute_info,
            "amount": amount,
            "total_rub": f"{total_rub:,.2f}".replace(",", " "),
            "total_usd": f"{total_usd:,.2f}".replace(",", " "),
            "total_eur": f"{total_eur:,.2f}".replace(",", " ")
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

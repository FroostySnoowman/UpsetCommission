import yaml
import paypalrestsdk
from paypalrestsdk import Invoice

with open('config.yml', 'r') as file:
    data = yaml.safe_load(file)

name = data["Invoice"]["NAME"]
website = data["Invoice"]["WEBSITE"]
tos = data["Invoice"]["TOS"]
fee = data["Invoice"]["FEE"]

async def create_invoice(auth: paypalrestsdk.Api, total: int, email: str = None):
    invoice_data = {
        "merchant_info": {
            "business_name": name,
            "website": website
        },
        "items": [
            {
                "name": "Service",
                "description": f"Service at {name}",
                "quantity": 1,
                "unit_price": {
                    "currency": "USD",
                    "value": total
                }
            }
        ],
        "note": f"This invoice is for your ticket at {name}.",
        "terms": tos,
        "payment_term": {
            "term_type": "NET_45"
        }
    }

    if fee > 0:
        invoice_data["items"].append({
            "name": "Fee",
            "description": "The fee for this invoice as per our TOS.",
            "quantity": 1,
            "unit_price": {
                "currency": "USD",
                "value": fee
            }
        })

    if email:
        invoice_data["billing_info"] = [{"email": email}]

    invoice = Invoice(invoice_data, api=auth)

    if invoice.create():
        invoice = Invoice.find(invoice['id'], api=auth)

        if invoice.send():
            return invoice.id
        else:
            return False
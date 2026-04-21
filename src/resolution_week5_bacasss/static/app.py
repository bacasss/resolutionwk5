from browser import document, html, aio, window
from browser.local_storage import storage as local_storage
import json

confirm = window.confirm

def toggletheme(event):
    if "dark" in document.body.class_name:
        document.body.class_name = ""
    else:
        document.body.class_name = "dark"
document["theme"].bind("click", toggletheme)

api_key = None
if "api_key" in local_storage:
    api_key = local_storage["api_key"]

async def register(event):
    name = document["name"].value
    req = await aio.post(
        "/register",
        headers={
            "Content-Type": "application/json"
        },
        data=json.dumps({"name": name})
    )
    if req.status == 200:
        result = json.loads(req.data)
        key = result["api_key"]
        global api_key
        api_key = key
        local_storage["api_key"] = key
        document["registered"].text = "registered, key saved."
    else:
        document["registered"].text = "error registering"

def registerclick(event):
    aio.run(register(event))
document["register"].bind("click", registerclick)

async def loaditems():
    if api_key is None:
        return
    document["loading"].style.display = "block"
    req = await aio.get("/items", headers={"x-api-key": api_key})
    document["loading"].style.display = "none"
    if req.status == 200:
        items = json.loads(req.data)
        container = document["itemlist"]
        container.clear()
        for item in items:
            p = html.P(f"{item['name']} (qty: {item['quantity']})")
            deletebtn = html.BUTTON("delete")
            async def delete(event, itemid=item["id"]):
                req = await aio.ajax("DELETE", f"/items/{itemid}", headers={"x-api-key": api_key})
                if req.status == 200:
                    await loaditems()
            def makedelete(itemid):
                def handler(event):
                    if not confirm("do you really want to delete this?"):
                        return
                    aio.run(delete(event, itemid))
                return handler
            deletebtn.bind("click", makedelete(item["id"]))
            p <= deletebtn
            container <= p

async def additem(event):
    if api_key is None:
        return
    name = document["itemname"].value
    qty = document["quantity"].value
    req = await aio.post("/items", headers={"x-api-key": api_key, "Content-Type": "application/json"}, data=json.dumps({"name": name, "quantity": int(qty), "defLow": 5}))
    if req.status == 200:
        await loaditems()

def addclick(event):
    aio.run(additem(event))
document["add"].bind("click", addclick)
aio.run(loaditems())
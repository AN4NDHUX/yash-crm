"""Nine independent immutable max+1 sequences and sales-record lifecycle."""
from test_workflow_rule_builder import app_scenario


def test_product_numbers_are_sequential_immutable_and_not_reused():
    out = app_scenario("""
    with TestClient(main.app) as c:
        c.post("/api/auth/signup", json={
            "name":"Numbers Owner","organization_name":"Products Sequences Org",
            "username":"numbers.owner","email":"numbers.owner@example.test",
            "password":"strong-password-123"})
        a=c.post("/api/products",json={"name":"Valve A"}).json()
        b=c.post("/api/products",json={"name":"Valve B"}).json()
        out["numbers"]=[a.get("record_number"),b.get("record_number")]
        out["edit_number"]=c.patch(f"/api/products/{a['id']}",json={"record_number":"PRD99999"}).status_code
        out["create_number"]=c.post("/api/products",json={"name":"Hijacked","record_number":"PRD44444"}).status_code
        out["edit_name"]=c.patch(f"/api/products/{a['id']}",json={"name":"Updated Valve"}).status_code
        out["delete"]=c.delete(f"/api/products/{b['id']}").status_code
        new=c.post("/api/products",json={"name":"Valve C"}).json()
        out["after_archive"]=new.get("record_number")
        out["active_products"]=[row["name"] for row in c.get("/api/products").json()["items"]]
        out["archived_get"]=c.get(f"/api/products/{b['id']}").status_code
        out["read"]=c.get(f"/api/products/{a['id']}").json()
    """)
    assert out["numbers"]==["PRD00001","PRD00002"],out
    assert out["after_archive"]=="PRD00003",out
    assert out["edit_number"]==out["create_number"]==422,out
    assert out["edit_name"]==200 and out["delete"]==200,out
    assert "Updated Valve" in out["active_products"] and "Valve C" in out["active_products"],out
    assert "Valve B" not in out["active_products"] and out["archived_get"]==404,out
    assert out["read"]["name"]=="Updated Valve" and out["read"]["record_number"]=="PRD00001",out


def test_paid_sales_modules_all_numbered_readonly_and_openable():
    out=app_scenario("""
    with TestClient(main.app) as c:
        c.post("/api/auth/signup",json={
            "name":"Sales Number Owner","organization_name":"Nine Modules Org",
            "username":"nine.modules","email":"nine.modules@example.test",
            "password":"strong-password-123"})
        with main.SessionLocal() as db:
            user=db.scalar(main.select(main.User).where(main.User.email=="nine.modules@example.test"))
            subscription=main._ensure_organization_subscription(db,user)
            subscription.plan_id=db.scalar(main.select(main.Plan.id).where(main.Plan.code=="professional"))
            subscription.status="Active"
            db.commit()
        account=c.post("/api/accounts",json={"name":"Legacy Client"}).json()
        deal=c.post("/api/deals",json={"name":"Proposal X","account_id":account["id"]}).json()
        paths=[
            ("price_books","PB",{"name":"Retail 2026"}),
            ("vendors","VND",{"name":"Vendor A"}),
            ("quotes","QT",{"name":"Quote A","deal_id":deal["id"]}),
        ]
        out["records"]={}
        for resource,prefix,payload in paths:
            created=c.post("/api/platform/"+resource,json=payload)
            assert created.status_code==201,(resource,created.text)
            out["records"][resource]=created.json()
        out["records"]["sales_orders"]=c.post("/api/platform/sales_orders",json={
            "name":"Sales A","quote_id":out["records"]["quotes"]["id"]}).json()
        out["records"]["purchase_orders"]=c.post("/api/platform/purchase_orders",json={
            "name":"Purchase A","vendor_id":out["records"]["vendors"]["id"]}).json()
        out["records"]["invoices"]=c.post("/api/platform/invoices",json={
            "name":"Invoice A","sales_order_id":out["records"]["sales_orders"]["id"]}).json()
        out["records"]["payments"]=c.post("/api/platform/payments",json={
            "name":"Receipt A","invoice_id":out["records"]["invoices"]["id"],
            "amount":10,"payment_date":"2026-10-10","status":"Received"}).json()
        out["checks"]={}
        for resource,item in out["records"].items():
            ident=item["id"]
            fetched=c.get(f"/api/platform/{resource}/{ident}")
            edited=c.patch(f"/api/platform/{resource}/{ident}",json={"name":"Updated "+resource})
            tampered=c.patch(f"/api/platform/{resource}/{ident}",json={"record_number":"BAD99999"})
            manual=c.post(f"/api/platform/{resource}",json={"name":"Injected","record_number":"BAD44444"})
            listing=c.get("/api/platform/"+resource)
            out["checks"][resource]={
                "read":fetched.status_code,"edit":edited.status_code,
                "tamper":tampered.status_code,"manual":manual.status_code,
                "listing":listing.status_code,
                "number":fetched.json().get("record_number"),
                "persisted":edited.json().get("record_number"),
            }
        quote=out["records"]["quotes"]
        out["quote_mutation"]=c.patch(f"/api/platform/quotes/{quote['id']}",json={
            "quote_number":"QT99999"}).status_code
        invoice=out["records"]["invoices"]
        out["invoice_mutation"]=c.patch(f"/api/platform/invoices/{invoice['id']}",json={
            "invoice_number":"INV99999"}).status_code
        original=out["records"]["price_books"]
        second=c.post("/api/platform/price_books",json={"name":"Retail B"}).json()
        out["next_price_book"]=second["record_number"]
        out["archive_status"]=c.delete("/api/platform/price_books/"+str(second["id"])).status_code
        third=c.post("/api/platform/price_books",json={"name":"Retail C"}).json()
        out["post_archive"]=third["record_number"]
        out["archived_lookup"]=c.get("/api/platform/price_books/"+str(second["id"])).status_code
    """)
    prefixes={"price_books":"PB","vendors":"VND","quotes":"QT",
              "sales_orders":"SO","purchase_orders":"PO","invoices":"INV","payments":"PAY"}
    for resource,prefix in prefixes.items():
        row=out["checks"][resource]
        assert row["number"]==prefix+"00001",(resource,out)
        assert row["persisted"]==row["number"],(resource,out)
        assert (row["read"],row["edit"],row["tamper"],row["manual"],row["listing"])==(200,200,422,422,200),(resource,out)
    assert out["quote_mutation"]==out["invoice_mutation"]==422,out
    assert out["next_price_book"]=="PB00002" and out["post_archive"]=="PB00003",out
    assert out["archive_status"]==200 and out["archived_lookup"]==404,out

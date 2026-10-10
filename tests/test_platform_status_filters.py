"""Platform status filters use the authoritative module definitions."""
from app.platform_catalog import PLATFORM_RESOURCES
from test_workflow_rule_builder import app_scenario

EXPECTED = {
    "quotes": ["Draft", "Pending Approval", "Approved", "Sent", "Accepted", "Closed", "Cancelled"],
    "sales_orders": ["Draft", "Confirmed", "In Fulfilment", "Fulfilled", "Cancelled"],
    "purchase_orders": ["Draft", "Issued", "Partially Received", "Received", "Cancelled"],
    "invoices": ["Draft", "Issued", "Partially Paid", "Paid", "Overdue", "Void"],
    "payments": ["Pending", "Received", "Cleared", "Failed", "Refunded"],
}


def test_sales_module_statuses_match_catalog():
    for resource, expected in EXPECTED.items():
        fields = PLATFORM_RESOURCES[resource]["fields"]
        field = next(field for field in fields if field["key"] == "status")
        assert field["type"] == "select"
        assert field["options"] == expected


def test_filtering_uses_the_actual_module_status_and_respects_organization():
    out = app_scenario("""
    from app.platform_catalog import PLATFORM_RESOURCES
    with TestClient(main.app) as client:
        signup = client.post('/api/auth/signup', json={
            'name':'Status Filter Owner', 'organization_name':'Status Filter Workspace',
            'username':'status.filter.owner','email':'status.filter.owner@example.test',
            'password':'long-password-123'})
        assert signup.status_code == 201, signup.text
        with main.SessionLocal() as db:
            user=db.scalar(main.select(main.User).where(main.User.email=='status.filter.owner@example.test'))
            subscription=main._ensure_organization_subscription(db, user)
            professional=db.scalar(main.select(main.Plan).where(main.Plan.code=='professional'))
            subscription.plan_id=professional.id
            subscription.status='Active'
            org_id=main._organization_id_for_user(db,user.id)
            for resource in ('quotes','sales_orders','purchase_orders','invoices','payments'):
                definition=next(field for field in PLATFORM_RESOURCES[resource]['fields'] if field['key']=='status')
                for index,status in enumerate(definition['options']):
                    db.add(main.PlatformRecord(
                        resource=resource,title=resource+' '+status, status=status,
                        organization_id=org_id,owner_id=user.id,
                        data={'name':resource+' '+status,'status':status}))
            db.commit()
        for resource in ('quotes','sales_orders','purchase_orders','invoices','payments'):
            statuses=next(field for field in PLATFORM_RESOURCES[resource]['fields'] if field['key']=='status')['options']
            total=client.get('/api/platform/'+resource,params={'limit':100})
            assert total.status_code==200, (resource,total.text)
            out[resource]={'total':total.json()['total'],'statuses':{}}
            for status in statuses:
                response=client.get('/api/platform/'+resource,params={'status':status,'limit':100})
                assert response.status_code==200, (resource,status,response.text)
                out[resource]['statuses'][status] = {
                    'total':response.json()['total'],
                    'values':[row['status'] for row in response.json()['items']],
                }
    """)
    for resource, statuses in EXPECTED.items():
        assert out[resource]["total"] == len(statuses), (resource, out[resource])
        for status in statuses:
            result = out[resource]["statuses"][status]
            assert result == {"total": 1, "values": [status]}, (resource, status, result)

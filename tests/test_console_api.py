from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_readiness_and_capabilities(fake_redis):
    assert client.get('/ready').json() == {'status': 'ok', 'dependencies': {'redis': 'ok'}}
    capabilities = client.get('/meta/capabilities').json()
    assert capabilities['provider_mode'] == 'mock'
    assert capabilities['streaming'] is False
    assert 'mock' in capabilities['providers']


def test_team_discovery_excludes_secrets():
    client.post('/admin/session', headers={'Authorization': 'Bearer local-admin-token'})
    response = client.get('/admin/teams')
    assert response.status_code == 200
    assert len(response.json()['teams']) == 2
    assert 'api_key' not in response.text
    assert 'alpha-secret-key' not in response.text


def test_dev_routes_are_absent_without_flag():
    assert client.get('/dev/state').status_code == 404


def test_dev_controls_require_token_and_can_reset(fake_redis, monkeypatch):
    from app.api.dev import router

    monkeypatch.setenv('DEV_CONTROL_TOKEN', 'test-only-token')
    dev_app = FastAPI()
    dev_app.include_router(router)
    dev = TestClient(dev_app)
    assert dev.post('/dev/failures', json={'provider': 'mock', 'model': 'mock-smart-chat', 'mode': 'timeout', 'count': 1}).status_code == 403
    headers = {'X-Dev-Control-Token': 'test-only-token'}
    queued = dev.post('/dev/failures', headers=headers, json={'provider': 'mock', 'model': 'mock-smart-chat', 'mode': 'timeout', 'count': 1})
    assert queued.status_code == 200
    assert queued.json()['queued_failures']['mock-smart-chat'] == ['timeout']
    invalid = dev.post('/dev/failures', headers=headers, json={'provider': 'mock', 'model': 'mock-smart-chat', 'mode': 'timeout', 'count': 101})
    assert invalid.status_code == 422
    seeded = dev.post('/dev/teams/team_alpha/spend', headers=headers, json={'daily_usd': 5, 'monthly_usd': 5})
    assert seeded.status_code == 200
    assert dev.get('/dev/state', headers=headers).json()['spend']['team_alpha']['daily_usd'] == 5
    reset = dev.post('/dev/reset', headers=headers, json={'scopes': ['failures', 'budgets'], 'teams': ['team_alpha']})
    assert reset.status_code == 200
    state = dev.get('/dev/state', headers=headers).json()
    assert state['queued_failures'] == {}
    assert state['spend']['team_alpha']['daily_usd'] == 0


def test_readiness_rejects_unavailable_redis(fake_redis, monkeypatch):
    async def unavailable():
        raise ConnectionError('secret details')

    monkeypatch.setattr(fake_redis, 'ping', unavailable)
    response = client.get('/ready')
    assert response.status_code == 503
    assert response.json()['error'] == 'dependency_unavailable'
    assert 'secret details' not in response.text

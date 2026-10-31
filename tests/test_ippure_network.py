import threading
from types import SimpleNamespace

import httpx
import pytest

from server.network import NetworkMonitor


def monitor():
    runtime = SimpleNamespace(lock=threading.RLock(), active=None,
                              alive=lambda: False, egress_identity=lambda: (0, '', 'rule', 1))
    return NetworkMonitor(runtime)


def test_ippure_maps_false_attributes_without_losing_their_meaning(monkeypatch):
    network = monitor()
    calls = []
    def response(client, url):
        calls.append(url)
        return dict(ip='192.0.2.4', country='Japan', countryCode='JP', region='Tokyo',
                    city='Tokyo', isResidential=False, isBroadcast=False, asOrganization='Test network', asn=64500)
    monkeypatch.setattr(network, '_json', response)
    value = network.lookup('system')
    assert calls == ['https://my.ippure.com/v1/info']
    assert value['status'] == 'ok' and value['provider'] == 'ippure.com'
    assert value['is_residential'] is False and value['is_broadcast'] is False
    assert value['country_code'] == 'JP' and value['ip'] == '192.0.2.4'


@pytest.mark.parametrize('extra', [{}, {'isResidential': None, 'isBroadcast': 'false'}])
def test_missing_or_non_boolean_properties_remain_unknown(monkeypatch, extra):
    network = monitor()
    monkeypatch.setattr(network, '_json', lambda *args: {'ip': '2001:db8::1', 'country': 'Japan', **extra})
    value = network.lookup('system')
    assert value['status'] == 'partial'
    assert value['is_residential'] is None and value['is_broadcast'] is None
    assert value['family'] == 'IPv6'


def test_ippure_failure_does_not_silently_query_another_provider(monkeypatch):
    network = monitor()
    calls = []
    def failure(client, url):
        calls.append(url)
        raise httpx.ConnectError('unavailable')
    monkeypatch.setattr(network, '_json', failure)
    value = network.lookup('system')
    assert value['status'] == 'unavailable' and value['ip'] == ''
    assert value['is_residential'] is None and value['is_broadcast'] is None
    assert len(calls) == 1

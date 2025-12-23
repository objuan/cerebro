
import subprocess
import re
import os

from ibind import IbkrClient, IbkrWsClient,IbkrWsKey
from ibind.oauth.oauth1a import OAuth1aConfig
from ibind import ibind_logs_initialize

ibind_logs_initialize()

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

'''
client = IbkrClient(
    use_oauth=True,
    oauth_config=OAuth1aConfig(
        access_token='d73f3da37a901376941f',
        access_token_secret='UF/l0ecpVjDigUI4FXKq6KqAV0braTjPDelmdcdzeOU8tz7C33HWCYSMHlv8AenZou6e60DdwglCQpVfoTX+Xm0AC8MjJulrnPpv79BBE0I/EdBYQD5jL5yc2NTwQ84N6x3TQ1Rw5XinipxerAoLIBCDRTklsWghE6PA38qJ3X3DU7UWxLvDvILfFCXrAKuvXec3rlFlxxJHdXbv2BPHyn5T/CgV8/YsxZnxdtiKnnhHIekUtwhwj5OvWICVECKJkrJlddhdYnhXDKsAoyqC1Box/1JUkqfC2ZYoxrpBWzCsWFLvOQAreJN489B9a0v2AufH5jWDcM8Gz4W1FmQDXQ==',
        consumer_key='PICODEXCE',
        dh_prime='00ad47133ba59f013f5c05ebdd4274156eeb3d6f83a8bf3a12835b8ca8efd99e39dca74e9f86f4d0e856d63c7a4ffabe889e17213d9801f6d09268b9ecc61c7e5372d633d675123a52e5eb4d175a6a29f3148bd4a86496c261ecdc6e9df94c6080905ab5379fa906b0a50cb92713c93213400a8c8dd91bd5ffc7aec0e89d338c59cdbe09e8562d2d94f5cf70c0a3df6e7b222bb7b935ccbef8e6b503314ccce3695a39ae178ceb2c7f3d1261dee46c8d6ef25bec28c1d18fdd06fdb417bcdebcd4548e348e109425ed57edeb09a7dac218bf2925928449e25d4e042685a91ea945c3466d86257c2de1a6e2e26b6b5a360e6df4dd9196e995a9b0ed84145c347c7b',
        encryption_key_fp='C:/Lavoro/cerebro/py/interactive_broker/cert/private_encryption.pem',
        signature_key_fp='C:/Lavoro/cerebro/py/interactive_broker/cert/private_signature.pem'
    )
)
exit()
'''

'''
# Choose the WebSocket channel
ibkr_ws_key = IbkrWsKey.PNL

ws_client = IbkrWsClient(start=True)


# Subscribe to the PNL channel
ws_client.subscribe(channel=ibkr_ws_key.channel)

# Wait for new items in the PNL queue.
while True:
    while not ws_client.empty(ibkr_ws_key):
        print(ws_client.get(ibkr_ws_key))
'''


client = IbkrClient()

# Call some endpoints
print('\n#### check_health ####')
print(client.check_health())

print('\n\n#### tickle ####')
print(client.tickle().data)


print('\n#### get_accounts ####')
accounts = client.portfolio_accounts().data
client.account_id = accounts[0]['accountId']
print(client.account_id, accounts)


print('\n\n#### get_ledger ####')
ledger = client.get_ledger().data
for currency, subledger in ledger.items():
    print(f'\t Ledger currency: {currency}')
    print(f'\t cash balance: {subledger["cashbalance"]}')
    print(f'\t net liquidation value: {subledger["netliquidationvalue"]}')
    print(f'\t stock market value: {subledger["stockmarketvalue"]}')
    print()

print('\n#### get_positions ####')
positions = client.positions().data
for position in positions:
    print(f'\t Position {position["ticker"]}: {position["position"]} (${position["mktValue"]})')
    
#accounts = client.accounts().data
#print(accounts)

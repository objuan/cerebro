#https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/#run-gw
#https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/#start-step-two-copyBtn
#https://ndcdyn.interactivebrokers.com/sso/Login?action=OAUTH&RL=1&ip2loc=US
# user objuankenoby71
# pwd Alicepici1!

'''



https://github.com/nsirons/ibkr_web_client



PAPER
Consumer Key : PICODEXCE
certificati in folder
access token : d73f3da37a901376941f
Access Token Secret: UF/l0ecpVjDigUI4FXKq6KqAV0braTjPDelmdcdzeOU8tz7C33HWCYSMHlv8AenZou6e60DdwglCQpVfoTX+Xm0AC8MjJulrnPpv79BBE0I/EdBYQD5jL5yc2NTwQ84N6x3TQ1Rw5XinipxerAoLIBCDRTklsWghE6PA38qJ3X3DU7UWxLvDvILfFCXrAKuvXec3rlFlxxJHdXbv2BPHyn5T/CgV8/YsxZnxdtiKnnhHIekUtwhwj5OvWICVECKJkrJlddhdYnhXDKsAoyqC1Box/1JUkqfC2ZYoxrpBWzCsWFLvOQAreJN489B9a0v2AufH5jWDcM8Gz4W1FmQDXQ==
'''

'''
import easyib

ib = easyib.REST()  # default a https://localhost:5000
print(ib.get_accounts())
print(ib.get_bars("AAPL", period="1w", bar="1d"))
'''

import subprocess
import re
import os

'''
result = subprocess.run(["openssl", "dhparam", "-in", "dhparam.pem", "-text"], capture_output=True, text=True).stdout
match = re.search(r"(?:prime|P):\s*((?:\s*[0-9a-fA-F:]+\s*)+)", result)
print(re.sub(r"[\s:]", "", match.group(1)) if match else "No prime (P) value found.")
'''

cert = """
    DH Parameters: (2048 bit)
        prime:
            00:ad:47:13:3b:a5:9f:01:3f:5c:05:eb:dd:42:74:
            15:6e:eb:3d:6f:83:a8:bf:3a:12:83:5b:8c:a8:ef:
            d9:9e:39:dc:a7:4e:9f:86:f4:d0:e8:56:d6:3c:7a:
            4f:fa:be:88:9e:17:21:3d:98:01:f6:d0:92:68:b9:
            ec:c6:1c:7e:53:72:d6:33:d6:75:12:3a:52:e5:eb:
            4d:17:5a:6a:29:f3:14:8b:d4:a8:64:96:c2:61:ec:
            dc:6e:9d:f9:4c:60:80:90:5a:b5:37:9f:a9:06:b0:
            a5:0c:b9:27:13:c9:32:13:40:0a:8c:8d:d9:1b:d5:
            ff:c7:ae:c0:e8:9d:33:8c:59:cd:be:09:e8:56:2d:
            2d:94:f5:cf:70:c0:a3:df:6e:7b:22:2b:b7:b9:35:
            cc:be:f8:e6:b5:03:31:4c:cc:e3:69:5a:39:ae:17:
            8c:eb:2c:7f:3d:12:61:de:e4:6c:8d:6e:f2:5b:ec:
            28:c1:d1:8f:dd:06:fd:b4:17:bc:de:bc:d4:54:8e:
            34:8e:10:94:25:ed:57:ed:eb:09:a7:da:c2:18:bf:
            29:25:92:84:49:e2:5d:4e:04:26:85:a9:1e:a9:45:
            c3:46:6d:86:25:7c:2d:e1:a6:e2:e2:6b:6b:5a:36:
            0e:6d:f4:dd:91:96:e9:95:a9:b0:ed:84:14:5c:34:
            7c:7b
        generator: 2 (0x2)
-----BEGIN DH PARAMETERS-----
MIIBCAKCAQEArUcTO6WfAT9cBevdQnQVbus9b4OovzoSg1uMqO/Znjncp06fhvTQ
6FbWPHpP+r6InhchPZgB9tCSaLnsxhx+U3LWM9Z1EjpS5etNF1pqKfMUi9SoZJbC
Yezcbp35TGCAkFq1N5+pBrClDLknE8kyE0AKjI3ZG9X/x67A6J0zjFnNvgnoVi0t
lPXPcMCj3257Iiu3uTXMvvjmtQMxTMzjaVo5rheM6yx/PRJh3uRsjW7yW+wowdGP
3Qb9tBe83rzUVI40jhCUJe1X7esJp9rCGL8pJZKESeJdTgQmhakeqUXDRm2GJXwt
4abi4mtrWjYObfTdkZbplamw7YQUXDR8ewIBAg==
-----END DH PARAMETERS-----

"""

'''
print(cert)

match = re.search(r"(?:prime|P):\s*((?:\s*[0-9a-fA-F:]+\s*)+)", cert)
print(re.sub(r"[\s:]", "", match.group(1)) if match else "No prime (P) value found.")

exit()
'''

'''
os.environ["IBIND_USE_OAUTH "] = "True"
os.environ["IBIND_OAUTH1A_CONSUMER_KEY "] = "PICODEXCE"
os.environ["IBIND_OAUTH1A_ENCRYPTION_KEY_FP "] = 'C:/Lavoro/cerebro/py/interactive_broker/private_encryption.pem'
os.environ["IBIND_OAUTH1A_SIGNATURE_KEY_FP "] = 'C:/Lavoro/cerebro/py/interactive_broker/private_signature.pem'
os.environ["IBIND_OAUTH1A_ACCESS_TOKEN "] = 'd73f3da37a901376941f'
os.environ["IBIND_OAUTH1A_ACCESS_TOKEN_SECRET "] = 'UF/l0ecpVjDigUI4FXKq6KqAV0braTjPDelmdcdzeOU8tz7C33HWCYSMHlv8AenZou6e60DdwglCQpVfoTX+Xm0AC8MjJulrnPpv79BBE0I/EdBYQD5jL5yc2NTwQ84N6x3TQ1Rw5XinipxerAoLIBCDRTklsWghE6PA38qJ3X3DU7UWxLvDvILfFCXrAKuvXec3rlFlxxJHdXbv2BPHyn5T/CgV8/YsxZnxdtiKnnhHIekUtwhwj5OvWICVECKJkrJlddhdYnhXDKsAoyqC1Box/1JUkqfC2ZYoxrpBWzCsWFLvOQAreJN489B9a0v2AufH5jWDcM8Gz4W1FmQDXQ=='
os.environ["IBIND_OAUTH1A_DH_PRIME "] ='00ad47133ba59f013f5c05ebdd4274156eeb3d6f83a8bf3a12835b8ca8efd99e39dca74e9f86f4d0e856d63c7a4ffabe889e17213d9801f6d09268b9ecc61c7e5372d633d675123a52e5eb4d175a6a29f3148bd4a86496c261ecdc6e9df94c6080905ab5379fa906b0a50cb92713c93213400a8c8dd91bd5ffc7aec0e89d338c59cdbe09e8562d2d94f5cf70c0a3df6e7b222bb7b935ccbef8e6b503314ccce3695a39ae178ceb2c7f3d1261dee46c8d6ef25bec28c1d18fdd06fdb417bcdebcd4548e348e109425ed57edeb09a7dac218bf2925928449e25d4e042685a91ea945c3466d86257c2de1a6e2e26b6b5a360e6df4dd9196e995a9b0ed84145c347c7b'

'''
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
        encryption_key_fp='C:/Lavoro/cerebro/py/interactive_broker/private_encryption.pem',
        signature_key_fp='C:/Lavoro/cerebro/py/interactive_broker/private_signature.pem'
    )
)
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

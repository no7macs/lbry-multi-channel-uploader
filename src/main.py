import requests
import json
import os
import sqlite3
import time
import hashlib
import gc
import importlib
import dbCreate

progPath = os.path.dirname(os.path.abspath(__file__))

#grabs balance and unlocks supports is balance is insuficient
def checkBal(wallet) -> str:
    print('--waiting to check balance--')
    time.sleep(90)
    wallet = requests.post("http://localhost:5279", json={"method": "wallet_balance", "params": {"wallet_id": wallet}}).json()
    walletBal = float(wallet['result']['available'])
    print(walletBal)

    if(walletBal <= 1):
        print('--unlocking funds--')
        supports = requests.post("http://localhost:5279", json={"method": "support_list", "params": {"wallet_id": wallet, "page_size": 50}}).json()
        print(supports)
        for a in supports["result"]["items"]:
            requests.post("http://localhost:5279", json={"method": "support_abandon", "params": {"claim_id": a['claim_id'], "wallet_id": wallet}}).json()
        #checkBal(wallet)
    else:
        return(walletBal)
    return(walletBal)

#grabs channel list info
def getChannelList() -> dict:
    with open('./channelList.json', 'r') as jsonRaw:
        return json.load(jsonRaw)

#add uploaded to db
def insertNewUpload(wallet, channel, file, url) -> None:
    curr.execute(f"""INSERT INTO uploaded(wallet, channel_name, file_path, file_name, url) VALUES('{wallet}', '{channel}', '{file[0]}', '{file[1]}', '{url}')""")
    dataBase.commit()
    return()

#uploads video to lbry
def uploadToLBRY(channelName, channelId, walletName, acountId, uploadFee, contentTags, fundingAccounts, file) -> str:
    thumbnailScript = 'gifFirst3Sec'
    thumbnailUploadScript = 'lbry'
    thumbnailImport = importlib.import_module(f'scripts.thumbnail.{thumbnailScript}.{thumbnailScript}')
    thumbnailUploadImport = importlib.import_module(f'scripts.thumbnailUpload.{thumbnailUploadScript}.{thumbnailUploadScript}')
    thumbnail = thumbnailUploadImport.main(thumbnailImport.main(os.path.join(file[0], file[1])))
    name = str(hashlib.sha256(file[0].encode('utf-8').strip()).hexdigest())[:5] + str(os.path.splitext(os.path.basename(file[1]))[0])
    nameTable = name.maketrans("", "", " !@#$%^&*()_-+=[]:,<.>/?;:'\|")
    name = name.translate(nameTable)
    upload = requests.post("http://localhost:5279", json={"method": "publish", "params": {
                            "name": name, "bid": uploadFee, "file_path": os.path.join(file[0], file[1]), "title": os.path.splitext(os.path.basename(file[1]))[0], 
                            "tags": contentTags, "thumbnail_url": thumbnail, "channel_id": channelId, "account_id": acountId, "wallet_id": walletName, 
                            "funding_account_ids": fundingAccounts}}).json()
    if 'error' in upload.keys():
        checkBal(walletName)
        afterError = uploadToLBRY(channelName, channelId, walletName, acountId, uploadFee, contentTags, fundingAccounts, file)
        return(afterError)
    else:
        insertNewUpload(walletName, channelName, file, (upload["result"]["outputs"][0]["permanent_url"]))
        return(upload['result']['outputs'][0]['permanent_url'])

def main(channel, contentTags, fundingAccounts, contentFolders, uploadAmmount):
    global dataBase, curr
    dbCreate.__main()
    dataBase = sqlite3.connect(progPath + '/data/database/db.s3db')
    curr = dataBase.cursor()

    addWallet = requests.post("http://localhost:5279", json={"method": "wallet_add", "params": {'wallet_id':channel[2]}}).json()
    # for removing directories and files in channels in a channels ignore list
    fileList = []
    for d in (0, len(contentFolders)-1):
        for (root,dirs,files) in os.walk(contentFolders[d], topdown=True, followlinks=True):
            ignores = curr.execute(f"""SELECT ignore_location, ignore, ignore_type FROM ignore WHERE channel_name = '{channel[0]}' """).fetchall()
            for e in ignores:
                if e[0] == root:
                    if e[2] == 'dir':
                        dirs[:] = [g for g in dirs if g not in e[0]]
                    if e[2] == 'file':
                        files[:] = [f for f in files if not (e[1] == f and e[2] == 'file')]
            #combines root and name together if name does not have !qB in it and adds to list, otherwise add None (e), then removes every none in list (f) 
            fileList.extend(f for f in [([root.replace('\\', '/'), e]) if '.!qB' not in e else None for e in files] if f)
    #removes duplicates from uploaded table
    curr.execute(f"""CREATE TEMP TABLE a(file_name TEXT, file_path TEXT)""")
    for a in fileList:
        curr.execute(f"""INSERT INTO a(file_path, file_name) VALUES("{a[0]}", "{a[1]}")""")
    curr.execute(f"""DELETE FROM a WHERE file_path+file_name in (SELECT file_path+file_name FROM uploaded WHERE channel_name = '{channel[0]}')""")
    notUploaded = curr.execute(f"""SELECT file_path, file_name FROM a""").fetchall()
    curr.execute(f"""DROP TABLE a""")
    if len(notUploaded) > 0:
        url = uploadToLBRY(channelName = channel[0], channelId = channel[1], walletName = channel[2], acountId = channel[3], uploadFee = channel[4],
                            contentTags = contentTags, fundingAccounts = fundingAccounts, file = notUploaded[0])

    gc.collect()
    dataBase.close()
    return()

if __name__ == "__main__":
    main()
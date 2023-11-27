# -*- coding:utf-8 -*-
#!/usr/bin/env python3
import requests
import json
import os
import time
import sys
import qbittorrentapi
from log import get_logger

LOG = get_logger(__name__, 'INFO')

# change_torrent
if not os.path.exists('conf.json'):
    with open('conf.json', 'w', encoding='UTF-8') as w:
        w.write('{\n    "trackers_list_url":[\n        "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_all.txt",\n        "https://raw.githubusercontent.com/XIU2/TrackersListCollection/master/best.txt"\n    ],\n    "rpc_host":"",\n    "rpc_username":"",\n    "rpc_passwd":"",\n    "rpc_port":9092,\n    "proxy":"",\n    "filter_list": [\n        "htm", "html", "apk", "url", "直播大秀平台", "网址", "APP"\n    ]\n}')
    print('请先手动conf.json配置')
    sys.exit()

with open('conf.json', 'r', encoding='UTF-8') as r:
    conf = json.loads(r.read())

TrackersListUrl = conf['trackers_list_url']
# instantiate a Client using the appropriate WebUI configuration
conn_info = dict(
    host=conf['rpc_host'],
    port=conf['rpc_port'],
    username=conf['rpc_username'],
    password=conf['rpc_passwd']
)
proxies = {}
if conf['proxy']:
    proxies = {
        "http": "http://"+conf['proxy'],
        "https": "http://"+conf['proxy']
    }

qbt_client = qbittorrentapi.Client(**conn_info)


# the Client will automatically acquire/maintain a logged-in state
# in line with any request. therefore, this is not strictly necessary;
# however, you may want to test the provided login credentials.
try:
    qbt_client.auth_log_in()
except qbittorrentapi.LoginFailed as e:
    LOG.error(e)
    sys.exit()

# display qBittorrent info
LOG.info(f"qBittorrent: {qbt_client.app.version}")
LOG.info(f"qBittorrent Web API: {qbt_client.app.web_api_version}")
for k, v in qbt_client.app.build_info.items():
    LOG.info(f"{k}: {v}")

Filter_List = conf['filter_list']


def update_trackersList():
    TrackersList_text = ''
    for x in TrackersListUrl:
        req = requests.get(x, proxies=proxies)
        TrackersList_text += req.text

    TrackersList = [x for x in TrackersList_text.splitlines() if len(x) > 1]

    trackersList_json = {
        'last_time': time.time(),
        'TrackersList': TrackersList
    }

    with open('tracker_list.json', 'w+') as f:
        # f.write(TrackersList_text)
        json.dump(trackersList_json, f)  # 存储json文件
    return trackersList_json


def get_track_list():

    # 判断文件是否存在
    json_exists = os.path.exists('tracker_list.json')
    trackersList_json = ''

    if json_exists:  # 存在
        LOG.info('tracker_list.json 文件存在！')
        try:
            with open('tracker_list.json', 'r') as f:
                trackersList_json = json.load(f)  # 读取文件

        except Exception as e:
            pass
    else:  # 不存在
        LOG.info('tracker_list.json 文件不存在！')
        trackersList_json = update_trackersList()

    # 计算是否更新本地trackerlist缓存
    if (time.time() - trackersList_json['last_time']
        ) / 3600 > 12:  # trackersList更新时间大于于12个小时

        trackersList_json = update_trackersList()

    return trackersList_json


def filter_file(torrent):
    '''过滤垃圾文件'''
    files = qbt_client.torrents_files(torrent_hash=torrent.hash)
    # 过滤文件
    unwant_list = []
    for id, file in enumerate(files):
        _basename, _filename = os.path.split(str(file.name))
        # print(f"base:{_basename},filename:{_filename}")
        for f_s in Filter_List:
            if _filename.find(f_s) > -1:  # 不下载垃圾文件和文件名长度超过255位的文件
                unwant_list.append(file.index)
                LOG.info(f'不下载：{file.name}')
                break
        if len(_filename.encode('utf-8')) > 250:
            try:
                new_path = os.path.join(
                    _basename, str(file.index)+_filename[int(len(_filename)/2):])
                qbt_client.torrents_rename_file(
                    torrent_hash=torrent.hash, old_path=file.name, new_path=new_path)
                LOG.info(f'重命名{file.name}=>{new_path}')
            except Exception as e:
                LOG.error(f'{torrent.name} 重命名 {file.name} {str(e)}')
                pass

    if len(unwant_list) > 0:
        torrent_priority(torrent, unwant_list)


def torrent_priority(torrent, unwant_list):
    try:
        qbt_client.torrents_file_priority(
            torrent_hash=torrent.hash,
            file_ids=unwant_list,
            priority=0
        )
    except Exception as e:
        LOG.error(f'{torrent.name} {str(e)}')
        pass


def torrent_add_trackers(torrent, trackersList):
    try:
        qbt_client.torrents_add_trackers(
            torrent_hash=torrent.hash, urls=trackersList)
        LOG.info(f'{torrent.name}已添加trackers')
    except Exception as e:
        LOG.error(f'{torrent.name} {str(e)}')
        pass


if __name__ == "__main__":
    trackersList_json = get_track_list()
    trackersList = trackersList_json['TrackersList']
    for torrent in qbt_client.torrents_info():
        filter_file(torrent)  # 过滤垃圾文件
        '''非私种添加tracker'''
        is_private = qbt_client.torrents_properties(
            torrent_hash=torrent.hash).is_private
        if not is_private:
            torrent_add_trackers(torrent, trackersList)

    qbt_client.auth_log_out()
    sys.exit()

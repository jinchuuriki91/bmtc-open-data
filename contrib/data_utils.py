# Python requests
import logging
import requests
from requests.exceptions import HTTPError
from rest_framework import status
from bs4 import BeautifulSoup
from envparse import env

# Django imports
from django.utils import timezone


logger = logging.getLogger(__name__)


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_3) AppleWebKit\
        /537.36 (KHTML, like Gecko) Chrome/72.0.3626.96 Safari/537.36"
}


def aggregate_bmtc_gs(page_to, page_from=0):
    result = []
    dt_now = timezone.now()
    for page in range(page_from, page_to + 1):
        try:
            result.extend(parse_bmtc_gs(page))
        except HTTPError:
            continue
    total_seconds = (timezone.now() - dt_now).seconds
    logger.info("Aggregator took %s seconds" % total_seconds)
    return result


def parse_bmtc_gs(page):

    def _calc_seconds(param):
        temp = param.split(" ")[0].split(":")
        return timezone.timedelta(
            hours=int(temp[0]),
            minutes=int(temp[1])).seconds

    def _clean(param):
        return param.text.split("\n")[2].strip()

    count = page * 20
    base_url = "%s?select=gens&count=%s&page=%s"
    url = base_url % (env('TIMETABLE_DETAILS'), count, page)
    logger.info(url)
    dt_now = timezone.now()
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    logger.info("Request took %s seconds" % (timezone.now() - dt_now).seconds)
    soup = BeautifulSoup(resp.content, features="html.parser")
    tbody = soup.find_all('table')[1].find("tbody")
    if tbody.text.strip("\n") == " ":
        raise Exception("Bad Data")
    trs = tbody.find_all('tr')
    result = []
    for tr in trs[1:19]:
        temp = {}
        try:
            tds = tr.find_all('td')
            # get route_no, origin, destination, journey time and distance
            ps = tds[0].find_all('p')
            temp["route_no"] = _clean(ps[0])
            temp["origin"] = _clean(ps[1])
            temp["destination"] = _clean(ps[2])
            temp["journey_time_sec"] = _calc_seconds(_clean(ps[3]))
            temp["journey_distance_km"] = _clean(ps[4]).split(" ")[0]
            temp["bus_stops"] = []
            busstop_meta = ps[5].find_all('a')[0]["href"][22:36].replace("'", "").split(",")  # noqa
            temp["route_id"] = busstop_meta[0]
            url = "%s?routeid=%s&busno=%s" % (
                env('BUSSTOP_LIST'), busstop_meta[0], temp["route_no"])
            try:
                logger.info(url)
                resp = requests.get(url)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.content, features="html.parser")
                table = soup.find_all("table")[2]
                for tr in table.find("tbody").find_all("tr"):
                    _tds = tr.find_all("td")
                    temp["bus_stops"].append({
                        "name": _tds[0].text,
                        "fare_stage": True if _tds[0].text == "Y" else False
                    })
            except Exception as exc:
                logger.error(exc)

            temp["dep_from_origin"] = tds[1].text.split(",")
            temp["arr_at_destination"] = tds[2].text.split(",")
            temp["dep_from_destination"] = tds[3].text.split(",")
            temp["arr_at_origin"] = tds[4].text.split(",")
            result.append(temp)
        except IndexError:
            continue
    return result


def get_stopname_search(pattern):
    result = []
    resp = requests.get(
        "%s/%s" % (env('STOPNAME_SEARCH'), pattern),
        headers=HEADERS)
    if resp.status_code == status.HTTP_200_OK:
        result = resp.json()
    return result


def get_route_search(pattern):
    result = []
    resp = requests.get(
        "%s/%s" % (env('ROUTE_SEARCH'), pattern),
        headers=HEADERS)
    if resp.status_code == status.HTTP_200_OK:
        result = resp.json()
    return result


def get_bus_category():
    result = []
    resp = requests.get(
        env('BUS_CATEGORY'),
        headers=HEADERS)
    if resp.status_code == status.HTTP_200_OK:
        result = resp.json()
    return result

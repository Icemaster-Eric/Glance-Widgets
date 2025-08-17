import contextlib
from typing import AsyncIterator, TypedDict
import time
from datetime import datetime
import json
import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, FileResponse
from starlette.routing import Route
from starlette.templating import Jinja2Templates
from bs4 import BeautifulSoup, Tag


with open("anime_lists.json", "r") as f:
    anime_lists: dict[str, list[str]] = json.load(f)

with open("calendars.json", "r") as f:
    calendars: dict = json.load(f)

templates = Jinja2Templates("templates")


class State(TypedDict):
    http_client: httpx.AsyncClient


@contextlib.asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[State]:
    async with httpx.AsyncClient() as client:
        yield {"http_client": client}


async def anime_schedule(request: Request):
    timezone = request.query_params.get("timezone")  # IANA Time Zone
    if timezone is None:
        timezone = "Etc/UTC"
    else:
        timezone = timezone
    
    anime_list = request.query_params.get("list")
    if anime_list is not None:
        anime_list = anime_lists.get(anime_list)

    full_list = request.query_params.get("full") == "true"

    client: httpx.AsyncClient = request.state.http_client

    schedule = []

    resp = await client.get(
        "https://www.livechart.me/schedule",
        cookies={
            "preferences": f'{{"time_zone":"{timezone}","titles":"english"}}',
            "preferences.schedule": '{"layout":"timetable","start":"today","sort":"release_date","sort_dir":"asc","included_marks":{"completed":true,"rewatching":true,"watching":true,"planning":true,"considering":true,"paused":false,"dropped":false,"skipping":false,"unmarked":true}}',
        },
    )
    soup = BeautifulSoup(resp.text, "lxml")
    for day in soup.find_all("div", class_="lc-timetable-day"):
        if not isinstance(day, Tag):
            continue

        day_date = day.find("div", class_="lc-timetable-day__heading flex")
        if not isinstance(day_date, Tag):
            break  # placeholder day thing
        day_date = day_date.get_text(" ", strip=True)

        day_data = {"day": day_date, "anime": []}

        # find anime of the day
        for anime_timeslot in day.find_all("div", class_="lc-timetable-timeslot"):
            if not isinstance(anime_timeslot, Tag):
                continue
            if "hidden" in anime_timeslot.attrs["class"]:
                continue

            anime_time = anime_timeslot.find("span", class_="lc-time")
            if not isinstance(anime_time, Tag):
                raise ValueError("Anime missing time information")
            anime_time = anime_time.get_text()

            anime_timestamp = anime_timeslot.find("time")
            if not isinstance(anime_timestamp, Tag):
                raise ValueError("Anime missing timestamp information")
            anime_timestamp = int(anime_timestamp.attrs["data-timestamp"])  # type: ignore

            # potentially multiple anime in same timeslot
            for anime in anime_timeslot.find_all(
                "div", class_="lc-timetable-anime-block"
            ):
                if not isinstance(anime, Tag):
                    continue  # not being broadcasted due to reasons:tm: (too lazy to parse)

                anime_image = anime.find("img")
                if not isinstance(anime_image, Tag):
                    raise ValueError("Anime missing image information")

                anime_image = anime_image.attrs.get("srcset")
                if not isinstance(anime_image, str):
                    raise ValueError("Anime missing image information")
                anime_image = anime_image.split(" ")[-2]

                anime_title = anime.find("a", class_="lc-tt-anime-title")
                if not isinstance(anime_title, Tag):
                    raise ValueError("Anime missing title information")
                anime_title = anime_title.get_text()

                anime_episode = anime.find("a", class_="lc-tt-release-label")
                if not isinstance(anime_episode, Tag):
                    raise ValueError("Anime missing episode information")
                anime_episode = anime_episode.get_text()

                if anime_list is not None:
                    if anime_title not in anime_list:
                        continue

                day_data["anime"].append(
                    {
                        "title": anime_title,
                        "episode": anime_episode,
                        "time": anime_time,
                        "timestamp": anime_timestamp,
                        "image": anime_image,
                    }
                )

        schedule.append(day_data)

        if not full_list:
            break

    if not schedule[0]["anime"]:
        schedule = []

    return templates.TemplateResponse(
        request,
        "anime-schedule.html",
        {"schedule": schedule, "current_time": time.time()},
        headers={"Widget-Title": "Anime Schedule", "Widget-Content-Type": "html"},
        media_type="text/html",
    )


def get_calendar(request: Request):
    calendar = request.query_params.get("calendar")
    if calendar is None or (calendar := calendars.get(calendar)) is None:
        return HTMLResponse("<p class='color-negative'>Error: calendar not found</p>")
    
    current_datetime = datetime.now()
    current_date = {
        "year": current_datetime.year,
        "month": current_datetime.strftime("%B"),
        "day": current_datetime.strftime("%A"),
        "day_of_month": current_datetime.day
    }

    no_calendar = False
    for month in calendar:
        if month["month"] == current_datetime.strftime("%B"):
            break
    else:
        no_calendar = True

    return templates.TemplateResponse(
        request,
        "calendar.html",
        {"calendar": calendar, "current_date": current_date, "int": int, "no_calendar": no_calendar},
        headers={"Widget-Title": "Calendar", "Widget-Content-Type": "html"},
        media_type="text/html"
    )


app = Starlette(
    routes=[
        Route("/anime-schedule", anime_schedule),
        Route("/calendar", get_calendar)
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)

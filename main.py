import contextlib
from typing import AsyncIterator, TypedDict
import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from urllib.parse import unquote
from bs4 import BeautifulSoup, Tag


class State(TypedDict):
    http_client: httpx.AsyncClient


@contextlib.asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[State]:
    async with httpx.AsyncClient() as client:
        yield {"http_client": client}


async def anime_schedule(request: Request):
    timezone = request.query_params.get("timezone") # IANA Time Zone
    if timezone is None:
        timezone = "Etc/UTC"
    else:
        timezone = unquote(timezone)

    client: httpx.AsyncClient = request.state.http_client

    schedule = []

    resp = await client.get(
        "https://www.livechart.me/schedule",
        cookies={
            "preferences": f'{{"time_zone":"{timezone}","titles":"english"}}',
            "preferences.schedule": '{"layout":"timetable","start":"today","sort":"release_date","sort_dir":"asc","included_marks":{"completed":true,"rewatching":true,"watching":true,"planning":true,"considering":true,"paused":false,"dropped":false,"skipping":false,"unmarked":true}}'
        }
    )
    soup = BeautifulSoup(resp.text, "lxml")
    for week in soup.find_all("div", class_="lc-timetable-day"):
        if not isinstance(week, Tag):
            continue

        week_date = week.find("div", class_="lc-timetable-day__heading flex")
        if not isinstance(week_date, Tag):
            break # placeholder day thing
        week_date = week_date.get_text(" ", strip=True)

        week_data = {
            "day": week_date,
            "anime": []
        }

        # find anime of the week
        for anime_timeslot in week.find_all("div", class_="lc-timetable-timeslot"):
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
            anime_timestamp = int(anime_timestamp.attrs["data-timestamp"]) # type: ignore

            # potentially multiple anime in same timeslot
            for anime in anime_timeslot.find_all("div", class_="lc-timetable-anime-block"):
                if not isinstance(anime, Tag):
                    continue # not being broadcasted due to reasons:tm: (too lazy to parse)

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

                week_data["anime"].append({
                    "title": anime_title,
                    "episode": anime_episode,
                    "time": anime_time,
                    "timestamp": anime_timestamp,
                    "image": anime_image
                })
        
        schedule.append(week_data)

    return JSONResponse(schedule)


app = Starlette(
    routes=[
        Route("/anime", endpoint=anime_schedule)
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)

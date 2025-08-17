# Glance Widgets
An API for my own custom Glance widgets.

## Widgets
- **Anime Schedule Extension**
    Options:
    - `timezone` - allows you to set your time zone. Optional, defaults to `Etc/UTC`.
    - `list` - name of your anime list in `anime_lists.json`. Optional.
    - `full` - whether to show the full anime schedule for the entire week. Optional.

    ```yaml
    - type: extension
        url: https://glance-widgets.coolify.hutao.rip/anime-schedule
        allow-potentially-dangerous-html: true
        parameters:
            timezone: Etc/UTC # IANA Time Zone
            list: my_list # filter for the anime you're interested in
            full: false # full week schedule
        cache: 6h
    ```

- **Calendar**
    Options:
    - A
    - B
    ```yaml
    ```

- **To-Do List**
    Options:
    - A
    - B
    ```yaml
    ```

# Officiële Bekendmakingen for Home Assistant

Official notices of Dutch municipalities, provinces and water boards that are about
a place near you, from [officielebekendmakingen.nl](https://www.officielebekendmakingen.nl):
building and felling permits, event permits, traffic decrees, zoning plans and more.

- Get a **notification** when a notice is published near your home.
- See the notices **on the map**, at the place they are about.
- Follow **several locations**, each with its own radius and notice types.

No account or API key is needed.

## Why

I built this integration because I wanted to keep track of the permit applications
for the upcoming renovation projects on my building.

## Installation

1. Add this repository to [HACS](https://hacs.xyz) as a custom repository of type
   _Integration_, then download **Officiële Bekendmakingen**.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and pick
   **Officiële Bekendmakingen**.
4. Pick a location and a radius on the map. It starts at your home with 500 m.

Add the integration again for another location. Change a location with
**Reconfigure**.

| Setting      | Meaning                                                    |
| ------------ | ---------------------------------------------------------- |
| Name         | The name of the device, such as _Bekendmakingen thuis_     |
| Location     | The position and the radius to follow                      |
| Notice types | The types to follow, such as `omgevingsvergunning`. Empty follows all types |
| Period       | How many days a notice stays, 30 by default                |

## Entities

Every location is a device with these entities.

| Entity              | What it shows                                                  |
| ------------------- | -------------------------------------------------------------- |
| `sensor` Notices    | The number of notices in the period. The attribute `notices` lists the newest 20 |
| `event` New notice  | Fires once for every new notice, with the notice as attributes |
| `geo_location`      | One entity per notice, at the place it is about, with the distance in metres |

The notices that are already published when you add a location do not fire the
event. Notices published while Home Assistant was off do, at the next start.

A notice has these attributes: `identifier`, `title`, `type`, `authority`,
`publication`, `published`, `abstract`, `url`, `activities`, `location` and
`distance`.

### Notification for a new notice

```yaml
triggers:
  - trigger: state
    entity_id: event.bekendmakingen_thuis_new_notice
    not_from: unavailable
actions:
  - action: notify.mobile_app_phone
    data:
      title: "{{ trigger.to_state.attributes.type }} at {{ trigger.to_state.attributes.distance }} m"
      message: "{{ trigger.to_state.attributes.title }}"
      data:
        url: "{{ trigger.to_state.attributes.url }}"
```

### Notices on the map

Add a map card with the geolocation source `officiele_bekendmakingen`:

```yaml
type: map
geo_location_sources:
  - officiele_bekendmakingen
entities:
  - zone.home
```

## How it works

Every hour the integration searches the
[SRU service](https://repository.overheid.nl/sru) of the government for notices in
the municipalities around the location, and keeps the notices whose area lies within
the radius. Notices without a location, such as regulations for a whole municipality,
are left out.

The municipalities are looked up once, when you add or reconfigure a location, with
the [PDOK geocoder](https://www.pdok.nl/pdok-locatieserver). It gets the position
rounded to about 100 m. The search itself only gets the names of the municipalities.

The notice texts are in Dutch, as published.

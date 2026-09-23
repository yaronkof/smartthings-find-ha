"""Constants for the SmartThings Find NextGen integration."""

DOMAIN = "smarttags_nextgen"

# Config entry keys
CONF_JSESSION_ID = "jsession_id"
CONF_COOKIE_HEADER = "cookie_header"
CONF_REGION = "region"
CONF_DEVICE_ID = "device_id"
# Integration services
SERVICE_LOCATE = "locate"
SERVICE_REFRESH = "refresh"

# Available operational regions as documented in Samsung backend servers
REGION_US_GENERAL = "prd-us"
REGION_EUROPE = "prd-eu"
REGION_ASIA = "prd-ap"
REGION_ASIA_2 = "prd-ap2"

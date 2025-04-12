"""Module providing a generate AI walk summary and route map."""

import uuid  # For generating unique filenames
import os  # For environment variables
import base64
from io import BytesIO
from enum import Enum
import folium  # For map visualization
from google import genai    # For Google Gemini API
from google.genai import types
from dotenv import load_dotenv  # For loading environment variables
from PIL import Image
import gpxpy
import gpxpy.gpx

OUTPUT_DIR = "outputs"

class Tone(Enum):
    """Class representing the tone of the journal entry."""
    FUN = "fun"
    SERIOUS = "serious"
    NEUTRAL = "neutral"
    POETIC = "poetic"
    TECHNICAL = "technical"
    CRINGE = "cringe"

class Focus(Enum):
    """Class representing the focus of the journal entry."""
    LANDMARKS = "landmarks"
    PARKS = "parks"
    BODIES_OF_WATER = "bodies_of_water"
    DISTANCE = "distance"
    TIME = "time"
    WEATHER = "weather"
    PLAYGROUNDS = "playgrounds"
    RESTAURANTS = "restaurants"
    COLORS = "colors"

class Length(Enum):
    """Class representing the length of the journal entry."""
    SHORT = "short"
    MEDIUM = "medium"
    DETAILED = "detailed"


# Example coordinates (latitude, longitude, timestamp)
coordinates = [(45.43025807431552, -75.70863767151599, "2025-04-11 10:00:00"),
               (45.429000675621126, -75.70033355227784, "2025-04-11 10:05:00"),
               (45.427502301655224, -75.6970719860959, "2025-04-11 10:08:00"),
               (45.42494970371503, -75.69519443975263, "2025-04-11 10:15:00"),
               (45.42386537938022, -75.69826288691044, "2025-04-11 10:20:00"),
               (45.42600388793949, -75.69912655813056, "2025-04-11 10:30:00")]

def get_journal_prompt(route_data, tone, focus, length):
    """Generate a journal prompt."""
    return f"""Summarize a walk as a {length} journal entry with a {tone} tone that followed these GPS
coordinates with timestamp: {str(route_data)} (don't report the coordinates or specific timestamps
back (start and end time okay). Try to focus on {focus} and otherwise identify one major landmark,
park, or body of water near each coordinate, and provide a fun fact about each (but don't
explicitly say fun fact each time). Comment on pace based on time and disctance covered. Incorpoate
the weather. Include a planned next walk based on the general area of this walk. Make the output
HTML formatted. Don't provide anything after the HTML, nor a blurb at start, just the journal
entry."""


def get_image_prompt(journal_entry):
    """Generate an image prompt based on the journal entry."""
    return f"""Generate a sketch-style image of one of the locations mentioned in this journal
entry: {journal_entry}"""


def parse_gpx_to_text(file_path):
    """
    Parses a GPX file and extracts relevant information as a text string.

    Args:
        file_path (str): The path to the GPX file.

    Returns:
        str: A text representation of the GPX data, including track points
             (latitude, longitude, elevation, time), waypoints, and route
             points. Returns None if the file cannot be opened or parsed.
    """
    try:
        with open(file_path, 'r') as gpx_file:
            gpx = gpxpy.parse(gpx_file)
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except gpxpy.gpx.GPXException as e:
        print(f"Error parsing GPX file: {e}")
        return None

    output_text = "GPX Data:\n"

    # Process tracks
    if gpx.tracks:
        output_text += "\nTracks:\n"
        for track in gpx.tracks:
            output_text += f"  Name: {track.name}\n"
            for segment in track.segments:
                output_text += "    Segment Points:\n"
                for point in segment.points:
                    output_text += f"      Lat: {point.latitude}, Lon: {point.longitude}, "
                    if point.elevation is not None:
                        output_text += f"Elev: {point.elevation}, "
                    if point.time is not None:
                        output_text += f"Time: {point.time.isoformat()} UTC\n"
    else:
        output_text += "\nNo tracks found.\n"

    # Process waypoints
    if gpx.waypoints:
        output_text += "\nWaypoints:\n"
        for waypoint in gpx.waypoints:
            output_text += f"  Name: {waypoint.name}, Lat: {waypoint.latitude}, Lon: {waypoint.longitude}\n"
            if waypoint.elevation is not None:
                output_text += f"    Elev: {waypoint.elevation}\n"
            if waypoint.time is not None:
                output_text += f"    Time: {waypoint.time.isoformat()} UTC\n"
            if waypoint.description:
                output_text += f"    Description: {waypoint.description}\n"
    else:
        output_text += "\nNo waypoints found.\n"

    # Process routes
    if gpx.routes:
        output_text += "\nRoutes:\n"
        for route in gpx.routes:
            output_text += f"  Name: {route.name}\n"
            output_text += "    Route Points:\n"
            for point in route.points:
                output_text += f"      Lat: {point.latitude}, Lon: {point.longitude}, "
                if point.elevation is not None:
                    output_text += f"Elev: {point.elevation}, "
                if point.time is not None:
                    output_text += f"Time: {point.time.isoformat()} UTC\n"
                if point.description:
                    output_text += f"      Description: {point.description}\n"
    else:
        output_text += "\nNo routes found.\n"

    return output_text

if __name__ == "__main__":
    load_dotenv()
    GPX_FILE_PATH = 'inputs/ottawa.gpx'  # Replace with the actual path to your GPX file
    parsed_route_data = parse_gpx_to_text(GPX_FILE_PATH)
    default_tone = Tone.POETIC
    default_focus = Focus.LANDMARKS
    default_length = Length.SHORT

    api_key = os.getenv("GEMINI_API_KEY")
    if api_key is None:
        raise ValueError("GEMINI_API_KEY environment variable not set.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if parsed_route_data:
        print(parsed_route_data)

        client = genai.Client(api_key=api_key)
        # Feed data to Gemini AI to generate journal entry
        JOURNAL_ENTRY = client.models.generate_content(model="gemini-2.0-flash",
                                                    contents=get_journal_prompt(parsed_route_data, default_tone, default_focus, default_length))

        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=get_image_prompt(JOURNAL_ENTRY.text),
            config=types.GenerateContentConfig(
            response_modalities=['Text', 'Image']
            )
        )

        HTML_IMAGE = ""

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image = Image.open(BytesIO((part.inline_data.data)))
                buffered = BytesIO()
                image.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')

                HTML_IMAGE += f'<img src="data:image/png;base64,{img_str}" alt="Generated Image"><br><br>'
            else:
                print("No image data found in the response.")

        # Output result for debugging
        # print(f"Walk Summary: {JOURNAL_ENTRY.text}")


        # Create a map centered around the first point
        m = folium.Map(location=(coordinates[0][0], coordinates[0][1]), zoom_start=14)

        # Add markers for each point
        for coord in coordinates:
            folium.Marker((coord[0], coord[1]), popup=f"Time: {coord[2]}").add_to(m)

        # Add a Polyline to connect the points
        folium.PolyLine([(coord[0], coord[1]) for coord in coordinates], color="blue", weight=5).add_to(m)

        # Get the HTML representation of the map
        MAP_HTML = m.get_root().render()

        # Inject the AI summary
        JOURNAL_HTML = f"<div style='font-family: Arial; margin: 20px;'><h2>Walk Summary</h2><p>\
            {JOURNAL_ENTRY.text}</p></div>"
        OUTPUT_HTML = MAP_HTML.replace("<body>", f"<body>{JOURNAL_HTML}{HTML_IMAGE}")

        MAP_FILEPATH = os.path.join(OUTPUT_DIR, f"trip_{uuid.uuid4().hex}.html")
        # Save the updated HTML directly
        with open(MAP_FILEPATH, "w", encoding="utf-8") as file:
            file.write(OUTPUT_HTML)

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import random
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw
import io
import requests
import time
import threading
import numpy as np
from collections import Counter
import json


with open('secrets.json') as f:
    secrets = json.load(f)

CLIENT_ID = secrets["CLIENT_ID"]
CLIENT_SECRET = secrets["CLIENT_SECRET"]
REDIRECT_URI = secrets["REDIRECT_URI"]
SCOPE = 'user-library-read user-read-playback-state user-modify-playback-state'

# Spotify authorization
sp_oauth = SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=SCOPE)
sp = spotipy.Spotify(auth_manager=sp_oauth)


def get_dominant_colors(image, num_colors=2):
    img_small = image.resize((100, 100))
    img_small = img_small.convert('RGB')

    pixels = np.array(img_small)
    pixels = pixels.reshape(-1, 3)

    count = Counter(map(tuple, pixels))
    most_common = count.most_common(num_colors)

    return [color for color, _ in most_common]


def create_gradient(width, height, color1, color2):
    gradient = Image.new('RGB', (width, height), color1)
    draw = ImageDraw.Draw(gradient)

    for y in range(height):
        ratio = y / height
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    return gradient


# Function to search for an artist and play a random song
def play_random_song(artist_name):
    result = sp.search(q=f'artist:{artist_name}', type='artist', limit=1)
    if not result['artists']['items']:
        print("Artist not found.")
        return

    artist_id = result['artists']['items'][0]['id']
    print(f"Found artist: {result['artists']['items'][0]['name']}")

    tracks = sp.artist_top_tracks(artist_id)['tracks']
    if not tracks:
        print("No tracks found for this artist.")
        return

    random_track = random.choice(tracks)
    track_name = random_track['name']
    track_url = random_track['external_urls']['spotify']
    album_cover_url = random_track['album']['images'][0]['url']
    track_id = random_track['id']
    track_duration = random_track['duration_ms'] / 1000
    artist_name = random_track['artists'][0]['name']

    print(f"Playing track: {track_name}")
    print(f"Track link: {track_url}")
    print(f"Album cover: {album_cover_url}")

    play_song(track_id, track_name, album_cover_url, track_duration, artist_name)


# Function to play a song in Spotify
def play_song(track_id, track_name, album_cover_url, track_duration, artist_name):
    devices = sp.devices()
    if not devices['devices']:
        print("No available devices for playback.")
        return

    device_id = devices['devices'][0]['id']

    window = tk.Tk()
    window.title("Spotify Player")
    window.geometry("500x600")

    cover_section = tk.Frame(window, width=500, height=450)
    cover_section.pack(fill="both", expand=True)

    response = requests.get(album_cover_url)
    image_data = io.BytesIO(response.content)
    cover_image = Image.open(image_data)

    dominant_colors = get_dominant_colors(cover_image)

    gradient_img = create_gradient(500, 450, dominant_colors[0], dominant_colors[1])
    gradient_photo = ImageTk.PhotoImage(gradient_img)

    background_label = tk.Label(cover_section, image=gradient_photo)
    background_label.place(x=0, y=0, relwidth=1, relheight=1)

    cover_image = cover_image.resize((300, 300))
    cover_photo = ImageTk.PhotoImage(cover_image)

    cover_label = tk.Label(cover_section, image=cover_photo, bg=None)
    cover_label.place(relx=0.5, rely=0.5, anchor="center")

    info_section = tk.Frame(window, bg="black", width=500, height=150)
    info_section.pack(fill="both", expand=True)

    track_label = tk.Label(info_section, text=track_name, fg="white", bg="black", font=("Helvetica", 14, "bold"),
                           anchor="w")
    track_label.place(relx=0.05, rely=0.2, anchor="w")

    artist_label = tk.Label(info_section, text=artist_name, fg="white", bg="black", font=("Helvetica", 12), anchor="w")
    artist_label.place(relx=0.05, rely=0.35, anchor="w")

    is_playing = False
    update_thread = None
    should_stop = False
    first_play = True


    play_icon = Image.open('play.png').resize((20, 20))
    pause_icon = Image.open('pause.png').resize((20, 20))

    play_icon_tk = ImageTk.PhotoImage(play_icon)
    pause_icon_tk = ImageTk.PhotoImage(pause_icon)

    # Increase button size by setting width and height
    play_button = tk.Button(info_section, image=play_icon_tk, bg="green", fg="white", width=30, height=30)
    play_button.place(relx=0.5, rely=0.5, anchor="center")

    progress_frame = tk.Frame(info_section, bg="black")
    progress_frame.place(relx=0.5, rely=0.85, anchor="center", width=380, height=20)

    progress_canvas = tk.Canvas(progress_frame, height=10, width=380, bg="#555555", highlightthickness=0)
    progress_canvas.pack(fill="both")

    progress_rect = progress_canvas.create_rectangle(0, 0, 0, 10, fill="#1DB954", outline="")

    # Adding a draggable progress dot
    progress_dot = progress_canvas.create_oval(0, 0, 10, 10, fill="white", outline="white", width=2)

    current_time_label = tk.Label(info_section, text="0:00", fg="white", bg="black", font=("Helvetica", 10))
    current_time_label.place(relx=0.05, rely=0.85, anchor="w")

    total_time_label = tk.Label(info_section, text=time.strftime('%M:%S', time.gmtime(track_duration)), fg="white",
                                bg="black", font=("Helvetica", 10))
    total_time_label.place(relx=0.95, rely=0.85, anchor="e")

    def update_progress_bar():
        nonlocal should_stop
        while not should_stop:
            try:
                if is_playing:
                    playback = sp.current_playback()
                    if playback and playback['is_playing']:
                        current_time = playback['progress_ms'] / 1000
                        progress_width = 5 + ((current_time / track_duration) * 370)
                        progress_canvas.coords(progress_rect, 0, 0, progress_width, 10)
                        progress_canvas.coords(progress_dot, progress_width - 5, 0, progress_width + 5, 10)
                        current_time_label.config(text=time.strftime('%M:%S', time.gmtime(current_time)))
                time.sleep(0.1)
            except Exception as e:
                print(f"Error updating progress bar: {e}")
                time.sleep(0.2)

    def on_progress_click(event):
        if is_playing:
            click_position = max(0, min(event.x - 5, 370)) / 370
            position_ms = int(track_duration * 1000 * click_position)
            try:
                sp.seek_track(position_ms)
            except Exception as e:
                print(f"Error seeking track: {e}")

    progress_canvas.bind("<Button-1>", on_progress_click)

    def drag_dot(event):
        if is_playing:
            click_position = max(0, min(event.x - 5, 370)) / 370
            position_ms = int(track_duration * 1000 * click_position)
            try:
                sp.seek_track(position_ms)
                progress_canvas.coords(progress_dot, event.x - 5, 0, event.x + 5, 10)
            except Exception as e:
                print(f"Error dragging progress dot: {e}")

    progress_canvas.tag_bind(progress_dot, "<B1-Motion>", drag_dot)

    def toggle_playback():
        nonlocal is_playing, update_thread, first_play

        try:
            if not is_playing:
                if first_play:
                    sp.start_playback(device_id=device_id, uris=[f'spotify:track:{track_id}'])
                    first_play = False
                else:
                    sp.start_playback(device_id=device_id)

                is_playing = True
                play_button.config(image=pause_icon_tk)

                if not update_thread or not update_thread.is_alive():
                    update_thread = threading.Thread(target=update_progress_bar, daemon=True)
                    update_thread.start()
            else:
                sp.pause_playback(device_id=device_id)
                is_playing = False
                play_button.config(image=play_icon_tk)
        except Exception as e:
            print(f"Error toggling playback: {e}")

    play_button.config(command=toggle_playback)

    def on_window_close():
        nonlocal should_stop
        should_stop = True
        try:
            if is_playing:
                sp.pause_playback()
        except:
            pass
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", on_window_close)

    window.after(500, toggle_playback)

    window.gradient_photo = gradient_photo
    window.cover_photo = cover_photo

    window.mainloop()


# To start the player, take input from user
artist_name = input("Enter artist name: ")
play_random_song(artist_name)

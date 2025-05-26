from ai_model import google_places_wrapper
import googlemaps
query = "Are there any McDonald's restaurants in walking distance?, nearby 9606 Glenacre Ln, Dallas, TX 75243, USA"


api_key = "AIzaSyAuj7gPxOpEWM6V6ckw0aErmR5FKS1-poI"

client = googlemaps.Client(api_key)

res = client.places(query,region='ca')
print(res)

google_places_wrapper(query)

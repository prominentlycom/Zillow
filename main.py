import requests

url = "https://zillow56.p.rapidapi.com/search_url"

querystring = {"url":"https://www.zillow.com/homes/for_sale/2_p/?searchQueryState=%7B%22pagination%22%3A%7B%22currentPage%22%3A2%7D%2C%22mapBounds%22%3A%7B%22west%22%3A-112.39143704189931%2C%22east%22%3A-110.78468655361806%2C%22south%22%3A32.79032628812945%2C%22north%22%3A33.7227901388417%7D%2C%22isMapVisible%22%3Atrue%2C%22filterState%22%3A%7B%22con%22%3A%7B%22value%22%3Afalse%7D%2C%22apa%22%3A%7B%22value%22%3Afalse%7D%2C%22mf%22%3A%7B%22value%22%3Afalse%7D%2C%22ah%22%3A%7B%22value%22%3Atrue%7D%2C%22sort%22%3A%7B%22value%22%3A%22globalrelevanceex%22%7D%2C%22land%22%3A%7B%22value%22%3Afalse%7D%2C%22manu%22%3A%7B%22value%22%3Afalse%7D%2C%22apco%22%3A%7B%22value%22%3Afalse%7D%7D%2C%22isListVisible%22%3Atrue%7D","page":"3"}

headers = {
	"X-RapidAPI-Key": "cad9458103mshe64bf73cf4954ebp1be8eajsn95afe237a166",
	"X-RapidAPI-Host": "zillow56.p.rapidapi.com"
}

response = requests.get(url, headers=headers, params=querystring)

print(response.json())
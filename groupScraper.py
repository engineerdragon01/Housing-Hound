import requests
from word2number import w2n
import re
import json
from requests_html import HTMLSession
from flask import Flask, render_template, request, redirect



url1 = 'https://m.facebook.com/groups/ucberkeleyoffcampushousing'
url2 = 'https://m.facebook.com/groups/1835635240040670/'
urlheader = 'https://m.facebook.com'



def filterPost(text):
    if len(text) <= 0:
        return False
    else:
        return True

def findNextPage(r):
    urlClassOuter = '.touchable'
    urlClassInner = '.primary'
    group_name = r.html.find(urlClassOuter)
    group_name = r.html.find(urlClassInner, first = True)
    print(group_name.links)
    return urlheader + group_name.links.pop()

def findGroupName(r):
    group_class = '._de1'
    group_name = r.html.find(group_class, first = True)
    return group_name.text


def scrapePage(r, posts):
    session = HTMLSession()
    global group_name
    group_name = findGroupName(r)
    post_class = '.story_body_container'
    for post in r.html.find(post_class):
        curr_poster = post.find('strong')[0].text
        curr_post = ''
        for para in post.find('p'):
            curr_post += para.text
        if filterPost(curr_post):
            posts[curr_poster]= curr_post


def scraperMain(start_url, pages = 2):
    session = HTMLSession()
    posts = {}

    for search in range(pages):
        req = session.get(start_url)
        print('Scraping page ' + start_url)
        scrapePage(req, posts)
        start_url = findNextPage(req)


    return posts



def parsePost(post):
    buyer_words = ['preferences', 'budget', 'max rent', 'a max of', 'looking']
    seller_words = ['furnished', 'subletting', 'opportunity', 'utilities', 'newly renovated', 'spots available', 'lease runs','lease starts']
    post = post.lower()
    is_buyer = any([buyer_word in post for buyer_word in buyer_words])
    is_seller = any([seller_word in post for seller_word in seller_words])
    if not is_buyer:
        return True
    else:
        return False

def extractInfo(post):
    post = post.lower()
    post_words = post.split()
    housing_info = {'bedrooms':'', 'bathrooms':'', 'price':''}
    dollar = '$'
    bedrooms = ['bed', 'beds', 'bedroom', 'bedrooms']
    bedroom_types = ['single', 'double', 'triple']
    bedroom_types_num = ['1', '2', '3']
    bathrooms = ['bath', 'baths', 'bathroom', 'bathrooms']
    #print(post_words)
    for index in range(len(post_words) - 1):
        if dollar in post_words[index] and len(housing_info['price']) == 0:
            housing_info['price'] = post_words[index]
        if any([word in post_words[index + 1] for word in bedrooms]) and len(housing_info['bedrooms']) == 0:
            try:
                housing_info['bedrooms'] = str(w2n.word_to_num(post_words[index]))
            except ValueError:
                #print('ValueError')
                pass
        if any([word in post_words[index + 1] for word in bathrooms]) and len(housing_info['bathrooms']) == 0:
            try:
                housing_info['bathrooms'] = str(w2n.word_to_num(post_words[index]))
            except ValueError:
                #print("ValueError")
                pass

    for index in range(len(bedroom_types)):
        if bedroom_types[index] in post_words and len(housing_info['bedrooms']) == 0:
            housing_info['bedrooms'] = bedroom_types_num[index]

    return housing_info

def parsePosts(url):
    posts = scraperMain(url, 5)
    housing_list = []
    for author, post in posts.items():
        if parsePost(post):
            post_info = extractInfo(post)
            for key in post_info.values():
                if len(key) > 0:
                    curr_housing = Housing(post_info['bedrooms'],
                                    post_info['bathrooms'],
                                    post_info['price'], author)
                    housing_list.append(curr_housing)
                    break
    return housing_list

class Housing:
    bedrooms_pref = 0
    bathrooms_pref = 0
    price_max = 0

    def __init__(self, bedrooms, bathrooms, price, author):
        self.bedrooms = bedrooms
        self.bathrooms = bathrooms
        self.price = re.sub('\D', '', price)
        self.setRank()
        self.author = author

    def __str__(self):
        return "Author: {}, Beds {}, Bathrooms {}, Price {}, Rank {}".format(self.author, self.bedrooms, self.bathrooms, self.price, self.rank)


    def setPrefs(self, bedrooms, bathrooms, price):
        Housing.bedrooms_pref = bedrooms
        Housing.bathrooms_pref = bathrooms
        Housing.price_max = price

    def setRank(self):
        self.rank = 3
        if len(self.bedrooms) > 0 and int(self.bedrooms) == self.bedrooms_pref:
            self.rank += 1
        if len(self.bathrooms) > 0 and int(self.bathrooms) == self.bathrooms_pref:
            self.rank += 1
        if len(self.price) > 0 and int(self.price_max) <= self.price_max:
            self.rank += 1

    def getRank(self):
        return self.rank

    def getPrice(self):
        if len(self.price) == 0:
            return float('inf')
        else:
            return int(self.price)

    def getBedrooms(self):
        if len(self.bedrooms) == 0:
            return "N/A"
        else:
            return self.bedrooms

    def getBathrooms(self):
        if len(self.bathrooms) == 0:
            return "N/A"
        else:
            return self.bathrooms

    def getPriceStr(self):
        if len(self.price) == 0:
            return "N/A"
        else:
            return int(self.price)

    def serialize(self):
        return [self.author, self.getBedrooms(), self.getBathrooms(), self.getPriceStr(),
        self.rank]


def sortHousing(h_list):
    return sorted(h_list, key= lambda x: (x.getRank(), -x.getPrice()), reverse = True)

def groupScraperMain(url, bedrooms_pref, bathrooms_pref, price_max):
    housing_list = parsePosts(url)
    housing_list[0].setPrefs(bedrooms_pref, bathrooms_pref, price_max)
    housing_list = sortHousing(housing_list)
    return housing_list


app = Flask(__name__)
url = url1
bedrooms_pref = 0
bathrooms_pref = 0
price_max = 0
group_name = ''

@app.route('/')
def a():
    housing_list = groupScraperMain(url, bedrooms_pref, bathrooms_pref, price_max)
    housing_list = sortHousing(housing_list)
    for h in housing_list:
        print(h)
    housing_master = [h.serialize() for h in housing_list]
    return render_template('main.html', housing_list = housing_master,
                            bedrooms = Housing.bedrooms_pref,
                            bathrooms = Housing.bathrooms_pref,
                            price = Housing.price_max,
                            group_name = group_name)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/about', methods = ['POST'])
def get_method():
    global url, bedrooms_pref, bathrooms_pref, price_max
    url, bedrooms_pref, bathrooms_pref, price_max = request.form['group_text'], request.form['bedroom_text'], request.form['bathroom_text'], request.form['price_text']
    return redirect('/')


if __name__ == '__main__':
    app.run(debug = True)

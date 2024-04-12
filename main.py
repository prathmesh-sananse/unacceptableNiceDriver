from collections import defaultdict
from flask import Flask, render_template, request, flash, redirect, jsonify
from neo4j import GraphDatabase, basic_auth
from datetime import datetime
import plotly.graph_objs as go

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'


# Establish connection to Neo4j database
driver = GraphDatabase.driver(uri='neo4j+s://4a2590fb.databases.neo4j.io', auth=basic_auth("neo4j","FtPcARjCVNgQ5bPw5oBfOy8hQCcXmL44zAJKuNWHpfI"))
session = driver.session()

@app.route('/', methods=['GET', 'POST'])
def index():
    page = request.args.get('page', default=1, type=int)
    page_size = 5
    if request.method == 'POST':
        search_term = request.form.get('search_term')
        blogs = search_blogs(search_term, page, page_size)
        return render_template('index.html', blogs=blogs, page=page, page_size=page_size)
    else:
        blogs = fetch_blogs(page, page_size)
        return render_template('index.html', blogs=blogs, page=page, page_size=page_size)

@app.route('/add_blog', methods=['GET', 'POST'])
def add_blog():
    if request.method == 'POST':
        blog_name = request.form['blog_name']
        preview = request.form['preview']
        url = request.form['url']
        owner = request.form['owner']
        category = request.form['category']
        publish_date = request.form['publish_date']
        expire_date = request.form['expire_date']
        relevance = request.form['relevance']
        target_audience = request.form['target_audience']
        region = request.form['region']

        # Custom Cypher query to create blog node and relationships
        query = """
        MERGE (b:Blog {name: $blog_name, preview: $preview, url: $url, owner: $owner, 
                      publish_date: $publish_date, expire_date: $expire_date})
        MERGE (c:Category {name: $category})
        MERGE (r:Relevance {name: $relevance})
        MERGE (t:TargetAudience {name: $target_audience})
        MERGE (re:Region {name: $region})
        MERGE (b)-[:BELONGS_TO]->(c)
        MERGE (b)-[:HAS_RELEVANCE]->(r)
        MERGE (b)-[:TARGETS]->(t)
        MERGE (b)-[:BELONGS_TO_REGION]->(re)
        """
        session.run(query, blog_name=blog_name, preview=preview, url=url, owner=owner,
                    category=category, publish_date=publish_date, expire_date=expire_date,
                    relevance=relevance, target_audience=target_audience, region=region)

        flash('Blog added successfully!')
        return redirect('/')
    else:
      # Fetching dropdown options from Neo4j database
        category_options = session.run("MATCH (c:Category) RETURN c.name AS category")
        relevance_options = session.run("MATCH (r:Relevance) RETURN r.name AS relevance")
        target_audience_options = session.run("MATCH (t:TargetAudience) RETURN t.name AS target_audience")
        region_options = session.run("MATCH (re:Region) RETURN re.name AS region")

        return render_template('add_blog.html', category_options=category_options, 
                                              relevance_options=relevance_options, 
                                              target_audience_options=target_audience_options, 
                                              region_options=region_options)

def fetch_blogs(page, page_size):
    query = """
    MATCH (b:Blog)-[:BELONGS_TO]->(category:Category)
    MATCH (b)-[:BELONGS_TO_REGION]->(region:Region)
    MATCH (b)-[:HAS_RELEVANCE]->(relevance:Relevance)
    MATCH (b)-[:TARGETS]->(target:TargetAudience)
    RETURN b.name AS name, b.url AS url, category.name AS category, 
           b.publish_date AS publish_date, b.expire_date AS expire_date, b.preview AS preview, b.owner AS owner, 
           region.name AS region, relevance.name AS relevance, 
           collect(target.name) AS target_audience
    ORDER BY b.name
    SKIP $skip
    LIMIT $limit
    """
    data = session.run(query, skip=(page - 1) * page_size, limit=page_size)
    return process_data(data)

def search_blogs(search_term, page, page_size):
    query = """
    MATCH (b:Blog)-[:BELONGS_TO]->(category:Category)
    MATCH (b)-[:BELONGS_TO_REGION]->(region:Region)
    MATCH (b)-[:HAS_RELEVANCE]->(relevance:Relevance)
    MATCH (b)-[:TARGETS]->(target:TargetAudience)
    WHERE b.name = $search_term OR category.name = $search_term OR region.name = $search_term OR relevance.name = $search_term OR target.name = $search_term
    RETURN b.name AS name, b.url AS url, category.name AS category, 
           b.publish_date AS publish_date, b.expire_date AS expire_date, b.preview AS preview, b.owner AS owner, 
           region.name AS region, relevance.name AS relevance, 
           collect(target.name) AS target_audience
    ORDER BY b.name
    SKIP $skip
    LIMIT $limit
    """
    data = session.run(query, search_term=search_term, skip=(page - 1) * page_size, limit=page_size)
    return process_data(data)

def process_data(data):
    blogs = []
    for record in data:
        blog = {
            "name": record["name"],
            "url": record["url"],
            "publish_date": record["publish_date"],
            "expire_date": record["expire_date"],
            "preview": record["preview"],
            "owner": record["owner"],
            "category": record["category"],
            "region": record["region"],
            "relevance": record["relevance"], 
            "target_audience": record["target_audience"]
        }

        if isinstance(blog["relevance"], list) and len(blog["relevance"]) > 1:
            blog["relevance"] = ", ".join(blog["relevance"])  

        if isinstance(blog["target_audience"], list) and len(blog["target_audience"]) > 1:
            blog["target_audience"] = ", ".join(blog["target_audience"])  

        blogs.append(blog)

    sorted_blogs = sorted(blogs, key=lambda x: x["name"])
    return sorted_blogs

@app.route('/fetch_options')
def fetch_options():
    categories_query = "MATCH (c:Category) RETURN c.name AS name"
    categories_result = session.run(categories_query)
    categories = [record['name'] for record in categories_result]

    audience_query = "MATCH (a:TargetAudience) RETURN a.name AS name"
    audience_result = session.run(audience_query)
    audience = [record['name'] for record in audience_result]

    relevance_query = "MATCH (r:Relevance) RETURN r.name AS name"
    relevance_result = session.run(relevance_query)
    relevance = [record['name'] for record in relevance_result]

    region_query = "MATCH (re:Region) RETURN re.name AS name"
    region_result = session.run(region_query)
    regions = [record['name'] for record in region_result]

    return jsonify(categories=categories, audience=audience, relevance=relevance, regions=regions)


@app.route('/visualisation')
def visualisation():
  current_year= datetime.now().year

  query = """
  MATCH (b:blog) 
  WHERE datetime({year: $year}) <= b.publish_date <= datetime({year: $year + 1})
  RETURN date(datetime({year: $year, month: date(b.publish_date).month, day: 1})) as month, count(b) as num_blogs 
  ORDER BY month 
  """

  data= session.run(query, year=current_year)
  months=[]
  num_blogs=[]
  for record in data:
    months.append(record['month'])
    num_blogs.append(record['num_blogs'])

  fig = go.Figure(data=go.Scatter(x=months, y=num_blogs, mode='lines+markers'))
  fig.update_layout(title='Total Number of blogs published per month', xaxis_title='Month', yaxis_title='Number of blogs')

  return render_template('visualisation.html', plot=fig.to_html())

if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.run(host='0.0.0.0', port=80, debug=True)
from collections import defaultdict
from flask import Flask, render_template, request, flash, redirect, jsonify
from neo4j import GraphDatabase, basic_auth
from datetime import datetime
import plotly.graph_objs as go
import networkx as nx

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
    # Query to retrieve total number of blogs published each month
    monthly_query = """
    MATCH (b:Blog) 
    RETURN date(datetime({year: 2024, month: date(b.publish_date).month, day: 1})) as month, count(b) as num_blogs 
    ORDER BY month 
    """

    # Execute monthly query
    monthly_data = session.run(monthly_query)
    monthly_months = []
    monthly_num_blogs = []
    for record in monthly_data:
        monthly_months.append(record['month'].strftime('%Y-%m-%d'))
        monthly_num_blogs.append(record['num_blogs'])

    # Plotly graph data for monthly blogs
    monthly_graph_data = [{
        'x': monthly_months,
        'y': monthly_num_blogs,
        'type': 'bar',
        'name': 'Monthly Blogs',
        'marker': {'color': 'rgb(158,202,225)'}
    }]

    # Create Plotly layout for monthly graph
    monthly_layout = {
        'title': 'Number of Blogs per Month',
        'xaxis': {'title': 'Month'},
        'yaxis': {'title': 'Number of Blogs'}
    }

    # Query to retrieve number of blogs per category
    category_query = """
    MATCH (b:Blog)-[:BELONGS_TO]->(c:Category)
    RETURN c.name AS category, count(b) AS num_blogs
    """

    # Execute category query
    category_data = session.run(category_query)
    category_labels = []
    category_num_blogs = []
    for record in category_data:
        category_labels.append(record['category'])
        category_num_blogs.append(record['num_blogs'])

    # Plotly graph data for category blogs
    category_graph_data = [{
        'x': category_labels,
        'y': category_num_blogs,
        'type': 'bar',
        'name': 'Category Blogs',
        'marker': {'color': 'rgb(255, 183, 50)'}
    }]

    # Create Plotly layout for category graph
    category_layout = {
        'title': 'Number of Blogs per Category',
        'xaxis': {'title': 'Category'},
        'yaxis': {'title': 'Number of Blogs'}
    }

    # Query to retrieve number of blogs per region
    region_query = """
    MATCH (b:Blog)-[:BELONGS_TO_REGION]->(r:Region)
    RETURN r.name AS region, count(b) AS num_blogs
    """

    # Execute region query
    region_data = session.run(region_query)
    region_labels = []
    region_num_blogs = []
    for record in region_data:
        region_labels.append(record['region'])
        region_num_blogs.append(record['num_blogs'])

    # Plotly graph data for region blogs
    region_graph_data = [{
        'x': region_labels,
        'y': region_num_blogs,
        'type': 'bar',
        'name': 'Region Blogs',
        'marker': {'color': 'rgb(50, 255, 50)'}
    }]

    # Create Plotly layout for region graph
    region_layout = {
        'title': 'Number of Blogs per Region',
        'xaxis': {'title': 'Region'},
        'yaxis': {'title': 'Number of Blogs'}
    }

    # Query to retrieve number of blogs per owner
    owner_query = """
    MATCH (b:Blog)
    RETURN b.owner AS owner, count(b) AS num_blogs
    """

    # Execute owner query
    owner_data = session.run(owner_query)
    owner_labels = []
    owner_num_blogs = []
    for record in owner_data:
        owner_labels.append(record['owner'])
        owner_num_blogs.append(record['num_blogs'])

    # Plotly graph data for owner blogs
    owner_graph_data = [{
        'x': owner_labels,
        'y': owner_num_blogs,
        'type': 'bar',
        'name': 'Owner Blogs',
        'marker': {'color': 'rgb(255, 50, 50)'}
    }]

    # Create Plotly layout for owner graph
    owner_layout = {
        'title': 'Number of Blogs per Owner',
        'xaxis': {'title': 'Owner'},
        'yaxis': {'title': 'Number of Blogs'}
    }

    # Query to retrieve number of blogs per target audience
    audience_query = """
    MATCH (b:Blog)-[:TARGETS]->(a:TargetAudience)
    RETURN a.name AS audience, count(b) AS num_blogs
    """

    # Execute audience query
    audience_data = session.run(audience_query)
    audience_labels = []
    audience_num_blogs = []
    for record in audience_data:
        audience_labels.append(record['audience'])
        audience_num_blogs.append(record['num_blogs'])

    # Plotly graph data for audience blogs
    audience_graph_data = [{
        'x': audience_labels,
        'y': audience_num_blogs,
        'type': 'bar',
        'name': 'Target Audience Blogs',
        'marker': {'color': 'rgb(50, 50, 255)'}
    }]

    # Create Plotly layout for audience graph
    audience_layout = {
        'title': 'Number of Blogs per Target Audience',
        'xaxis': {'title': 'Target Audience'},
        'yaxis': {'title': 'Number of Blogs'}
    }


    network_query = """
    MATCH (b:Blog)-[:BELONGS_TO]->(c:Category)
    MATCH (b)-[:BELONGS_TO_REGION]->(re:Region)
    MATCH (b)-[:HAS_RELEVANCE]->(r:Relevance)
    MATCH (b)-[:TARGETS]->(t:TargetAudience)
    RETURN DISTINCT b.name AS blog, c.name AS category, re.name AS region, r.name AS relevance, t.name AS target_audience
    """

    # Execute query
    network_data = session.run(network_query)

    # Create nodes for the network graph
    nodes = set()
    edges=[]
    for record in network_data:
      nodes.add(record['blog'])
      nodes.add(record['category'])
      nodes.add(record['relevance'])
      nodes.add(record['target_audience'])
      nodes.add(record['region'])
      edges.append((record['blog'], record['category']))
      edges.append((record['blog'], record['relevance']))
      edges.append((record['blog'], record['target_audience']))
      edges.append((record['blog'], record['region']))

    G = nx.Graph()
    
    # Create Plotly network graph
    network_graph_data = [{
      'type': 'scatter',
      'x': [edge[0] for edge in edges],
      'y': [edge[1] for edge in edges],
      'mode': 'markers',
      'hoverinfo': 'x+y',
      'marker': {'size':10}
    }]
  
    # Create Plotly layout
    network_layout = {
        'title': 'Network Graph of Blogs, Categories, Target Audience, Relevance and Regions',
        'showlegend': False
    }
  
    return render_template('visualisation.html', monthly_graph_data=monthly_graph_data, monthly_layout=monthly_layout, category_graph_data=category_graph_data, category_layout=category_layout, region_graph_data=region_graph_data, region_layout=region_layout, owner_graph_data=owner_graph_data, owner_layout=owner_layout, audience_graph_data=audience_graph_data, audience_layout=audience_layout,network_graph_data=network_graph_data, network_layout=network_layout)

if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.run(host='0.0.0.0', port=80, debug=True)
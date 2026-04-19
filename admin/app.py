from fastapi import FastAPI, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
import json
import os
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Reiizam Admin Panel")
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory='templates')

BASE_DIR = Path(__file__).parent
PRODUCTS_PATH = BASE_DIR / 'products.json'
CONFIG_PATH = BASE_DIR / 'config.json'

class Config(BaseModel):
    STORE_NAME: str
    WA_NUMBER: str
    RESTART_DELAY_SECONDS: int
    IDLE_RESET_SECONDS: int
    ADMIN_USER: str = 'admin'
    ADMIN_PASS: str = 'admin'

class Category(BaseModel):
    title: str
    icon: str
    description: str
    items: List[Dict[str, Any]]
    category_notes: List[str] = []
    logo: str = ''



def get_products() -> Dict[str, Any]:
    if PRODUCTS_PATH.exists():
        with open(PRODUCTS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_products(products: Dict[str, Any]):
    with open(PRODUCTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(products, f, indent=2, ensure_ascii=False)

def get_config() -> Config:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Ensure admin credentials exist
            if 'ADMIN_USER' not in data: data['ADMIN_USER'] = 'admin'
            if 'ADMIN_PASS' not in data: data['ADMIN_PASS'] = 'admin'
            return Config(**data)
    return Config(
        STORE_NAME=os.getenv('STORE_NAME', 'reiizam store'),
        WA_NUMBER=os.getenv('WA_NUMBER', '62882000414738'),
        RESTART_DELAY_SECONDS=5,
        IDLE_RESET_SECONDS=900
    )

def save_config(config: Config):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config.dict(), f, indent=2, ensure_ascii=False)

def verify_auth(request: Request) -> bool:
    config = get_config()
    # Check cookie-based auth first (from login form)
    auth_cookie = request.cookies.get('auth')
    if auth_cookie == 'logged_in':
        return True
    
    # Also support Basic Auth for API calls
    auth = request.headers.get('Authorization')
    if auth and auth.startswith('Basic '):
        import base64
        cred = base64.b64decode(auth[6:]).decode().split(':')
        return cred[0] == config.ADMIN_USER and cred[1] == config.ADMIN_PASS
    
    return False

@app.get('/')
async def dashboard(request: Request):
    if not verify_auth(request):
        return RedirectResponse(url='/login', status_code=302)
    products = get_products()
    config = get_config()
    
    num_categories = len(products)
    num_products = sum(len(cat.get('items', [])) for cat in products.values())
    
    return templates.TemplateResponse('dashboard.html', {
        'request': request, 
        'num_categories': num_categories, 
        'num_products': num_products,
        'config': config
    })

@app.get('/login')
async def login_page(request: Request, logout: str = None):
    response = templates.TemplateResponse('login.html', {'request': request})
    if logout:
        response.delete_cookie('auth')
    return response

@app.post('/login')
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    config = get_config()
    if username == config.ADMIN_USER and password == config.ADMIN_PASS:
        response = RedirectResponse(url='/', status_code=302)
        response.set_cookie('auth', 'logged_in', httponly=True, max_age=3600)
        return response
    return templates.TemplateResponse('login.html', {'request': request, 'error': 'Username atau password salah'})

@app.get('/logout')
async def logout(request: Request):
    response = RedirectResponse(url='/login?logout=1', status_code=302)
    response.delete_cookie('auth')
    return response

@app.get('/products')
async def products_page(request: Request):
    if not verify_auth(request):
        return RedirectResponse(url='/login', status_code=302)
    products = get_products()
    return templates.TemplateResponse('products.html', {'request': request, 'products': products})

@app.post('/products/add_category')
async def add_category(request: Request, title: str = Form(...), icon: str = Form(...), description: str = Form(...), logo: str = Form(None)):
    if not verify_auth(request):
        return JSONResponse({'error': 'Unauthorized'}, status_code=401)
    products = get_products()
    key = title.lower().replace(' ', '_')
    products[key] = Category(title=title, icon=icon, description=description, items=[], logo=logo or '').dict()
    save_products(products)
    return JSONResponse({'success': True})

@app.post('/products/edit_category')
async def edit_category(request: Request, key: str = Form(...), title: str = Form(...), icon: str = Form(...), description: str = Form(...), logo: str = Form(None)):
    if not verify_auth(request):
        return JSONResponse({'error': 'Unauthorized'}, status_code=401)
    products = get_products()
    if key in products:
        products[key]['title'] = title
        products[key]['icon'] = icon
        products[key]['description'] = description
        products[key]['logo'] = logo or ''
        save_products(products)
        return JSONResponse({'success': True})
    return JSONResponse({'error': 'Category not found'}, status_code=404)

@app.post('/products/delete_category')
async def delete_category(request: Request, key: str = Form(...)):
    if not verify_auth(request):
        return JSONResponse({'error': 'Unauthorized'}, status_code=401)
    products = get_products()
    products.pop(key, None)
    save_products(products)
    return JSONResponse({'success': True})

@app.post('/products/add_item')
async def add_item(request: Request, cat_key: str = Form(...), item_id: str = Form(...), name: str = Form(...), duration: str = Form(...), price: str = Form(...)):
    if not verify_auth(request):
        return JSONResponse({'error': 'Unauthorized'}, status_code=401)
    products = get_products()
    if cat_key not in products:
        return JSONResponse({'error': 'Category not found'}, status_code=400)
    new_item = {'id': item_id, 'name': name, 'duration': duration, 'price': price, 'notes': []}
    products[cat_key]['items'].append(new_item)
    save_products(products)
    return JSONResponse({'success': True})

@app.post('/products/delete_item')
async def delete_item(request: Request, cat_key: str = Form(...), item_id: str = Form(...)):
    if not verify_auth(request):
        return JSONResponse({'error': 'Unauthorized'}, status_code=401)
    products = get_products()
    if cat_key not in products:
        return JSONResponse({'error': 'Category not found'}, status_code=400)
    products[cat_key]['items'] = [item for item in products[cat_key]['items'] if item['id'] != item_id]
    save_products(products)
    return JSONResponse({'success': True})

@app.post('/products/edit_item')
async def edit_item(request: Request, cat_key: str = Form(...), item_id: str = Form(...), name: str = Form(...), duration: str = Form(...), price: str = Form(...)):
    if not verify_auth(request):
        return JSONResponse({'error': 'Unauthorized'}, status_code=401)
    products = get_products()
    if cat_key not in products:
        return JSONResponse({'error': 'Category not found'}, status_code=400)
    for item in products[cat_key]['items']:
        if item['id'] == item_id:
            item['name'] = name
            item['duration'] = duration
            item['price'] = price
            break
    save_products(products)
    return JSONResponse({'success': True})

@app.get('/config')
async def config_page(request: Request):
    if not verify_auth(request):
        return RedirectResponse(url='/login', status_code=302)
    config = get_config()
    return templates.TemplateResponse('config.html', {'request': request, 'config': config})

@app.post('/config')
async def save_config_page(request: Request, store_name: str = Form(...), wa_number: str = Form(...), restart_delay: int = Form(...), idle_reset: int = Form(...)):
    if not verify_auth(request):
        return JSONResponse({'error': 'Unauthorized'}, status_code=401)
    
    current_config = get_config()
    config = Config(
        STORE_NAME=store_name, 
        WA_NUMBER=wa_number, 
        RESTART_DELAY_SECONDS=restart_delay, 
        IDLE_RESET_SECONDS=idle_reset,
        ADMIN_USER=current_config.ADMIN_USER,
        ADMIN_PASS=current_config.ADMIN_PASS
    )
    save_config(config)
    return RedirectResponse(url='/config', status_code=302)

@app.post('/change_password')
async def change_password(request: Request, username: str = Form(...), old_pass: str = Form(...), new_pass: str = Form(...)):
    if not verify_auth(request):
        return RedirectResponse(url='/login', status_code=302)
    
    config = get_config()
    if username == config.ADMIN_USER and old_pass == config.ADMIN_PASS:
        config.ADMIN_PASS = new_pass
        save_config(config)
        response = RedirectResponse(url='/login?logout=1', status_code=302)
        response.delete_cookie('auth')
        return response
    
    return templates.TemplateResponse('config.html', {
        'request': request, 
        'config': config, 
        'error': 'Username atau password lama salah'
    })

@app.get('/export')
async def export():
    products = get_products()
    config = get_config().dict()
    return JSONResponse({'products': products, 'config': config})

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='localhost', port=8001)

from fastapi import APIRouter, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from dataclasses import dataclass, asdict
from typing import Dict, Any, List
from pathlib import Path
import shared_data

router = APIRouter()
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / 'templates'))

@dataclass
class Category:
    title: str
    icon: str
    description: str
    items: List[Dict[str, Any]]
    category_notes: List[str]
    logo: str = ''

    def dict(self):
        return asdict(self)

def verify_auth(request: Request) -> bool:
    # Check cookie-based auth first
    auth_cookie = request.cookies.get('auth')
    if auth_cookie == 'logged_in':
        return True
    
    # Support Basic Auth for API calls
    auth = request.headers.get('Authorization')
    if auth and auth.startswith('Basic '):
        import base64
        try:
            cred = base64.b64decode(auth[6:]).decode().split(':')
            return cred[0] == shared_data.CONFIG.get('ADMIN_USER') and cred[1] == shared_data.CONFIG.get('ADMIN_PASS')
        except:
            return False
    return False

@router.get('/')
async def dashboard(request: Request):
    if not verify_auth(request):
        return RedirectResponse(url='/login', status_code=302)
    
    num_categories = len(shared_data.PRODUCTS)
    num_products = sum(len(cat.get('items', [])) for cat in shared_data.PRODUCTS.values())
    
    # We create an object-like view of CONFIG for the template
    class ConfigView:
        def __init__(self, d):
            self.__dict__ = d
    
    return templates.TemplateResponse('dashboard.html', {
        'request': request, 
        'num_categories': num_categories, 
        'num_products': num_products,
        'config': ConfigView(shared_data.CONFIG)
    })

@router.get('/login')
async def login_page(request: Request, logout: str = None):
    response = templates.TemplateResponse('login.html', {'request': request})
    if logout:
        response.delete_cookie('auth')
    return response

@router.post('/login')
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == shared_data.CONFIG.get('ADMIN_USER') and password == shared_data.CONFIG.get('ADMIN_PASS'):
        response = RedirectResponse(url='/', status_code=302)
        response.set_cookie('auth', 'logged_in', httponly=True, max_age=3600*24)
        return response
    return templates.TemplateResponse('login.html', {'request': request, 'error': 'Username atau password salah'})

@router.get('/logout')
async def logout(request: Request):
    response = RedirectResponse(url='/login?logout=1', status_code=302)
    response.delete_cookie('auth')
    return response

@router.get('/products')
async def products_page(request: Request):
    if not verify_auth(request):
        return RedirectResponse(url='/login', status_code=302)
    return templates.TemplateResponse('products.html', {'request': request, 'products': shared_data.PRODUCTS})

@router.post('/products/add_category')
async def add_category(request: Request, title: str = Form(...), icon: str = Form(...), description: str = Form(...), logo: str = Form(None)):
    if not verify_auth(request):
        return JSONResponse({'error': 'Unauthorized'}, status_code=401)
    
    key = title.lower().replace(' ', '_')
    shared_data.PRODUCTS[key] = Category(title=title, icon=icon, description=description, items=[], category_notes=[], logo=logo or '').dict()
    shared_data.save_products(shared_data.PRODUCTS)
    return JSONResponse({'success': True})

@router.post('/products/edit_category')
async def edit_category(request: Request, key: str = Form(...), title: str = Form(...), icon: str = Form(...), description: str = Form(...), logo: str = Form(None)):
    if not verify_auth(request):
        return JSONResponse({'error': 'Unauthorized'}, status_code=401)
    
    if key in shared_data.PRODUCTS:
        shared_data.PRODUCTS[key]['title'] = title
        shared_data.PRODUCTS[key]['icon'] = icon
        shared_data.PRODUCTS[key]['description'] = description
        shared_data.PRODUCTS[key]['logo'] = logo or ''
        shared_data.save_products(shared_data.PRODUCTS)
        return JSONResponse({'success': True})
    return JSONResponse({'error': 'Category not found'}, status_code=404)

@router.post('/products/delete_category')
async def delete_category(request: Request, key: str = Form(...)):
    if not verify_auth(request):
        return JSONResponse({'error': 'Unauthorized'}, status_code=401)
    
    shared_data.PRODUCTS.pop(key, None)
    shared_data.save_products(shared_data.PRODUCTS)
    return JSONResponse({'success': True})

@router.post('/products/add_item')
async def add_item(request: Request, cat_key: str = Form(...), item_id: str = Form(...), name: str = Form(...), duration: str = Form(...), price: str = Form(...)):
    if not verify_auth(request):
        return JSONResponse({'error': 'Unauthorized'}, status_code=401)
    
    if cat_key not in shared_data.PRODUCTS:
        return JSONResponse({'error': 'Category not found'}, status_code=400)
    
    new_item = {'id': item_id, 'name': name, 'duration': duration, 'price': price, 'notes': []}
    shared_data.PRODUCTS[cat_key]['items'].append(new_item)
    shared_data.save_products(shared_data.PRODUCTS)
    return JSONResponse({'success': True})

@router.post('/products/delete_item')
async def delete_item(request: Request, cat_key: str = Form(...), item_id: str = Form(...)):
    if not verify_auth(request):
        return JSONResponse({'error': 'Unauthorized'}, status_code=401)
    
    if cat_key not in shared_data.PRODUCTS:
        return JSONResponse({'error': 'Category not found'}, status_code=400)
    
    shared_data.PRODUCTS[cat_key]['items'] = [item for item in shared_data.PRODUCTS[cat_key]['items'] if item['id'] != item_id]
    shared_data.save_products(shared_data.PRODUCTS)
    return JSONResponse({'success': True})

@router.post('/products/edit_item')
async def edit_item(request: Request, cat_key: str = Form(...), item_id: str = Form(...), name: str = Form(...), duration: str = Form(...), price: str = Form(...)):
    if not verify_auth(request):
        return JSONResponse({'error': 'Unauthorized'}, status_code=401)
    
    if cat_key not in shared_data.PRODUCTS:
        return JSONResponse({'error': 'Category not found'}, status_code=400)
    
    for item in shared_data.PRODUCTS[cat_key]['items']:
        if item['id'] == item_id:
            item['name'] = name
            item['duration'] = duration
            item['price'] = price
            break
            
    shared_data.save_products(shared_data.PRODUCTS)
    return JSONResponse({'success': True})

@router.get('/config')
async def config_page(request: Request):
    if not verify_auth(request):
        return RedirectResponse(url='/login', status_code=302)
        
    class ConfigView:
        def __init__(self, d):
            self.__dict__ = d
            
    return templates.TemplateResponse('config.html', {'request': request, 'config': ConfigView(shared_data.CONFIG)})

@router.post('/config')
async def save_config_page(request: Request, store_name: str = Form(...), wa_number: str = Form(...), restart_delay: int = Form(...), idle_reset: int = Form(...)):
    if not verify_auth(request):
        return JSONResponse({'error': 'Unauthorized'}, status_code=401)
    
    new_config = {
        'STORE_NAME': store_name, 
        'WA_NUMBER': wa_number, 
        'RESTART_DELAY_SECONDS': restart_delay, 
        'IDLE_RESET_SECONDS': idle_reset
    }
    shared_data.save_config(new_config)
    return RedirectResponse(url='/config', status_code=302)

@router.post('/change_password')
async def change_password(request: Request, username: str = Form(...), old_pass: str = Form(...), new_pass: str = Form(...)):
    if not verify_auth(request):
        return RedirectResponse(url='/login', status_code=302)
    
    if username == shared_data.CONFIG.get('ADMIN_USER') and old_pass == shared_data.CONFIG.get('ADMIN_PASS'):
        shared_data.save_config({'ADMIN_PASS': new_pass})
        response = RedirectResponse(url='/login?logout=1', status_code=302)
        response.delete_cookie('auth')
        return response
    
    class ConfigView:
        def __init__(self, d):
            self.__dict__ = d
            
    return templates.TemplateResponse('config.html', {
        'request': request, 
        'config': ConfigView(shared_data.CONFIG), 
        'error': 'Username atau password lama salah'
    })

@router.get('/export')
async def export():
    return JSONResponse({'products': shared_data.PRODUCTS, 'config': shared_data.CONFIG})

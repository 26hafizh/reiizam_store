from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from pathlib import Path
from typing import Optional
import shared_data

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / 'templates'))


# ── Auth ──────────────────────────────────────────────

def is_authed(request: Request) -> bool:
    if request.cookies.get('auth') == 'ok':
        return True
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Basic '):
        import base64
        try:
            u, p = base64.b64decode(auth[6:]).decode().split(':', 1)
            return u == shared_data.CONFIG.get('ADMIN_USER') and p == shared_data.CONFIG.get('ADMIN_PASS')
        except Exception:
            pass
    return False


def need_login():
    return RedirectResponse('/login', 302)


# ── Pages ─────────────────────────────────────────────

@router.get('/login')
async def login_page(request: Request, logout: str = None):
    resp = templates.TemplateResponse('login.html', {'request': request})
    if logout:
        resp.delete_cookie('auth')
    return resp


@router.post('/login')
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    cfg = shared_data.CONFIG
    if username == cfg.get('ADMIN_USER') and password == cfg.get('ADMIN_PASS'):
        resp = RedirectResponse('/', 302)
        resp.set_cookie('auth', 'ok', httponly=True, max_age=86400)
        return resp
    return templates.TemplateResponse('login.html', {'request': request, 'error': 'Username atau password salah'})


@router.get('/logout')
async def logout():
    resp = RedirectResponse('/login?logout=1', 302)
    resp.delete_cookie('auth')
    return resp


@router.get('/')
async def dashboard(request: Request):
    if not is_authed(request):
        return need_login()
    p = shared_data.PRODUCTS
    return templates.TemplateResponse('dashboard.html', {
        'request': request,
        'num_categories': len(p),
        'num_products': sum(len(c.get('items', [])) for c in p.values()),
        'config': shared_data.CONFIG,
    })


@router.get('/products')
async def products_page(request: Request):
    if not is_authed(request):
        return need_login()
    return templates.TemplateResponse('products.html', {
        'request': request,
        'products': shared_data.PRODUCTS,
    })


@router.get('/config')
async def config_page(request: Request):
    if not is_authed(request):
        return need_login()
    return templates.TemplateResponse('config.html', {
        'request': request,
        'config': shared_data.CONFIG,
    })


# ── API: Categories ───────────────────────────────────

@router.post('/api/category/add')
async def api_add_category(request: Request,
                           title: str = Form(...),
                           icon: str = Form('📦'),
                           description: str = Form(''),
                           logo: str = Form('')):
    if not is_authed(request):
        return JSONResponse({'error': 'Unauthorized'}, 401)

    key = title.lower().replace(' ', '_').replace('-', '_')
    if key in shared_data.PRODUCTS:
        return JSONResponse({'error': 'Kategori sudah ada'}, 400)

    shared_data.PRODUCTS[key] = {
        'title': title,
        'icon': icon,
        'description': description,
        'items': [],
        'category_notes': [],
        'logo': logo,
    }
    shared_data.save_products(shared_data.PRODUCTS)
    return JSONResponse({'ok': True, 'key': key})


@router.post('/api/category/edit')
async def api_edit_category(request: Request,
                            key: str = Form(...),
                            title: str = Form(...),
                            icon: str = Form('📦'),
                            description: str = Form(''),
                            logo: str = Form('')):
    if not is_authed(request):
        return JSONResponse({'error': 'Unauthorized'}, 401)
    if key not in shared_data.PRODUCTS:
        return JSONResponse({'error': 'Kategori tidak ditemukan'}, 404)

    cat = shared_data.PRODUCTS[key]
    cat['title'] = title
    cat['icon'] = icon
    cat['description'] = description
    if logo:  # Only update logo if a new one is provided
        cat['logo'] = logo
    shared_data.save_products(shared_data.PRODUCTS)
    return JSONResponse({'ok': True})


@router.post('/api/category/delete')
async def api_delete_category(request: Request, key: str = Form(...)):
    if not is_authed(request):
        return JSONResponse({'error': 'Unauthorized'}, 401)
    shared_data.PRODUCTS.pop(key, None)
    shared_data.save_products(shared_data.PRODUCTS)
    return JSONResponse({'ok': True})


# ── API: Items ────────────────────────────────────────

@router.post('/api/item/add')
async def api_add_item(request: Request,
                       cat_key: str = Form(...),
                       item_id: str = Form(...),
                       name: str = Form(...),
                       duration: str = Form(...),
                       price: str = Form(...)):
    if not is_authed(request):
        return JSONResponse({'error': 'Unauthorized'}, 401)
    if cat_key not in shared_data.PRODUCTS:
        return JSONResponse({'error': 'Kategori tidak ditemukan'}, 400)

    # Check duplicate ID
    for item in shared_data.PRODUCTS[cat_key]['items']:
        if item['id'] == item_id:
            return JSONResponse({'error': f'Item ID "{item_id}" sudah ada'}, 400)

    shared_data.PRODUCTS[cat_key]['items'].append({
        'id': item_id, 'name': name, 'duration': duration, 'price': price, 'notes': []
    })
    shared_data.save_products(shared_data.PRODUCTS)
    return JSONResponse({'ok': True})


@router.post('/api/item/edit')
async def api_edit_item(request: Request,
                        cat_key: str = Form(...),
                        item_id: str = Form(...),
                        name: str = Form(...),
                        duration: str = Form(...),
                        price: str = Form(...)):
    if not is_authed(request):
        return JSONResponse({'error': 'Unauthorized'}, 401)
    if cat_key not in shared_data.PRODUCTS:
        return JSONResponse({'error': 'Kategori tidak ditemukan'}, 400)

    for item in shared_data.PRODUCTS[cat_key]['items']:
        if item['id'] == item_id:
            item['name'] = name
            item['duration'] = duration
            item['price'] = price
            shared_data.save_products(shared_data.PRODUCTS)
            return JSONResponse({'ok': True})

    return JSONResponse({'error': 'Item tidak ditemukan'}, 404)


@router.post('/api/item/delete')
async def api_delete_item(request: Request,
                          cat_key: str = Form(...),
                          item_id: str = Form(...)):
    if not is_authed(request):
        return JSONResponse({'error': 'Unauthorized'}, 401)
    if cat_key not in shared_data.PRODUCTS:
        return JSONResponse({'error': 'Kategori tidak ditemukan'}, 400)

    shared_data.PRODUCTS[cat_key]['items'] = [
        i for i in shared_data.PRODUCTS[cat_key]['items'] if i['id'] != item_id
    ]
    shared_data.save_products(shared_data.PRODUCTS)
    return JSONResponse({'ok': True})


# ── API: Config ───────────────────────────────────────

@router.post('/api/config/save')
async def api_save_config(request: Request,
                          store_name: str = Form(...),
                          wa_number: str = Form(...),
                          idle_reset: int = Form(900)):
    if not is_authed(request):
        return JSONResponse({'error': 'Unauthorized'}, 401)

    shared_data.save_config({
        'STORE_NAME': store_name,
        'WA_NUMBER': wa_number,
        'IDLE_RESET_SECONDS': max(idle_reset, 60),
    })
    return JSONResponse({'ok': True})


@router.post('/api/config/password')
async def api_change_password(request: Request,
                              old_pass: str = Form(...),
                              new_pass: str = Form(...)):
    if not is_authed(request):
        return JSONResponse({'error': 'Unauthorized'}, 401)

    if old_pass != shared_data.CONFIG.get('ADMIN_PASS'):
        return JSONResponse({'error': 'Password lama salah'}, 400)

    shared_data.save_config({'ADMIN_PASS': new_pass})
    resp = JSONResponse({'ok': True, 'message': 'Password berhasil diubah. Silakan login ulang.'})
    resp.delete_cookie('auth')
    return resp


# ── API: Export ───────────────────────────────────────

@router.get('/api/export')
async def api_export(request: Request):
    if not is_authed(request):
        return JSONResponse({'error': 'Unauthorized'}, 401)
    return JSONResponse({'products': shared_data.PRODUCTS, 'config': shared_data.CONFIG})

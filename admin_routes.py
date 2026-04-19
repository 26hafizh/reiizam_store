import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import shared_data


def normalize_base_path(value: str | None) -> str:
    raw = (value or '').strip()
    if not raw:
        return '/reiizam-control-room'
    if not raw.startswith('/'):
        raw = f'/{raw}'
    raw = raw.rstrip('/')
    return raw or '/reiizam-control-room'


ADMIN_BASE_PATH = normalize_base_path(os.getenv('ADMIN_BASE_PATH'))
SESSION_COOKIE_NAME = 'reiizam_admin_session'
SESSION_TTL_SECONDS = max(int(os.getenv('ADMIN_SESSION_TTL_SECONDS', '43200')), 900)

router = APIRouter(prefix=ADMIN_BASE_PATH)
templates = Jinja2Templates(directory=str(Path(__file__).parent / 'templates'))


def build_admin_url(path: str = '') -> str:
    if not path:
        return f'{ADMIN_BASE_PATH}/'
    if not path.startswith('/'):
        path = f'/{path}'
    return f'{ADMIN_BASE_PATH}{path}'


def admin_username() -> str:
    return str(os.getenv('ADMIN_USERNAME') or shared_data.CONFIG.get('ADMIN_USER') or 'admin')


def password_hash_from_storage() -> str:
    return str(os.getenv('ADMIN_PASSWORD_HASH') or shared_data.CONFIG.get('ADMIN_PASS_HASH') or '')


def password_managed_by_env() -> bool:
    return bool(os.getenv('ADMIN_PASSWORD_HASH'))


def session_secret() -> str:
    return str(
        os.getenv('ADMIN_SESSION_SECRET')
        or os.getenv('BOT_TOKEN')
        or password_hash_from_storage()
        or shared_data.CONFIG.get('ADMIN_PASS')
        or 'reiizam-admin-session'
    )


def hash_password(password: str, *, salt: str | None = None, iterations: int = 390000) -> str:
    actual_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        actual_salt.encode('utf-8'),
        iterations,
    ).hex()
    return f'pbkdf2_sha256${iterations}${actual_salt}${digest}'


def verify_password_hash(password: str, stored_hash: str) -> bool:
    try:
        algorithm, raw_iterations, salt, expected = stored_hash.split('$', 3)
        if algorithm != 'pbkdf2_sha256':
            return False
        iterations = int(raw_iterations)
    except (TypeError, ValueError):
        return False

    candidate = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        iterations,
    ).hex()
    return hmac.compare_digest(candidate, expected)


def verify_admin_password(password: str) -> bool:
    stored_hash = password_hash_from_storage()
    if stored_hash:
        return verify_password_hash(password, stored_hash)

    legacy_password = str(shared_data.CONFIG.get('ADMIN_PASS') or '')
    return bool(legacy_password) and hmac.compare_digest(password, legacy_password)


def create_session_token() -> str:
    expires_at = int(time.time()) + SESSION_TTL_SECONDS
    payload = f'{admin_username()}|{expires_at}'
    signature = hmac.new(
        session_secret().encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return f'{payload}|{signature}'


def is_valid_session_token(token: str) -> bool:
    try:
        username, raw_expires_at, signature = token.split('|', 2)
        expires_at = int(raw_expires_at)
    except (AttributeError, ValueError):
        return False

    if not hmac.compare_digest(username, admin_username()):
        return False
    if expires_at < int(time.time()):
        return False

    payload = f'{username}|{expires_at}'
    expected_signature = hmac.new(
        session_secret().encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)


def is_authed(request: Request) -> bool:
    return is_valid_session_token(request.cookies.get(SESSION_COOKIE_NAME, ''))


def set_session_cookie(response: RedirectResponse, request: Request) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        create_session_token(),
        httponly=True,
        secure=request.url.scheme == 'https',
        samesite='strict',
        max_age=SESSION_TTL_SECONDS,
        path=ADMIN_BASE_PATH,
    )


def clear_session_cookie(response: RedirectResponse) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path=ADMIN_BASE_PATH)


def need_login() -> RedirectResponse:
    return RedirectResponse(build_admin_url('/login'), 302)


def render_template(
    request: Request,
    template_name: str,
    current_page: str,
    *,
    status_code: int = 200,
    **context,
):
    base_context = {
        'request': request,
        'current_admin_page': current_page,
        'admin_base_path': ADMIN_BASE_PATH,
        'admin_home_url': build_admin_url('/'),
        'admin_login_url': build_admin_url('/login'),
        'admin_products_url': build_admin_url('/products'),
        'admin_config_url': build_admin_url('/config'),
        'admin_logout_url': build_admin_url('/logout'),
        'admin_export_url': build_admin_url('/api/export'),
        'password_managed_by_env': password_managed_by_env(),
    }
    base_context.update(context)
    return templates.TemplateResponse(template_name, base_context, status_code=status_code)


@router.get('/login')
async def login_page(request: Request, logout: str | None = None):
    if is_authed(request):
        return RedirectResponse(build_admin_url('/'), 302)

    response = render_template(request, 'login.html', 'login')
    if logout:
        clear_session_cookie(response)
    return response


@router.post('/login')
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if hmac.compare_digest(username, admin_username()) and verify_admin_password(password):
        response = RedirectResponse(build_admin_url('/'), 302)
        set_session_cookie(response, request)
        return response

    return render_template(
        request,
        'login.html',
        'login',
        status_code=401,
        error='Username atau password salah',
    )


@router.get('/logout')
async def logout():
    response = RedirectResponse(build_admin_url('/login?logout=1'), 302)
    clear_session_cookie(response)
    return response


@router.get('/')
async def dashboard(request: Request):
    if not is_authed(request):
        return need_login()

    products = shared_data.PRODUCTS
    return render_template(
        request,
        'dashboard.html',
        'dashboard',
        num_categories=len(products),
        num_products=sum(len(category.get('items', [])) for category in products.values()),
        config=shared_data.CONFIG,
    )


@router.get('/products')
async def products_page(request: Request):
    if not is_authed(request):
        return need_login()

    return render_template(
        request,
        'products.html',
        'products',
        products=shared_data.PRODUCTS,
    )


@router.get('/config')
async def config_page(request: Request):
    if not is_authed(request):
        return need_login()

    return render_template(
        request,
        'config.html',
        'config',
        config=shared_data.CONFIG,
    )


@router.post('/api/category/add')
async def api_add_category(
    request: Request,
    title: str = Form(...),
    icon: str = Form('📦'),
    description: str = Form(''),
    logo: str = Form(''),
):
    if not is_authed(request):
        return JSONResponse({'error': 'Unauthorized'}, 401)

    key = shared_data.slugify_key(title)
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
async def api_edit_category(
    request: Request,
    key: str = Form(...),
    title: str = Form(...),
    icon: str = Form('📦'),
    description: str = Form(''),
    logo: str = Form(''),
):
    if not is_authed(request):
        return JSONResponse({'error': 'Unauthorized'}, 401)
    if key not in shared_data.PRODUCTS:
        return JSONResponse({'error': 'Kategori tidak ditemukan'}, 404)

    category = shared_data.PRODUCTS[key]
    category['title'] = title
    category['icon'] = icon
    category['description'] = description
    category['logo'] = logo
    shared_data.save_products(shared_data.PRODUCTS)
    return JSONResponse({'ok': True})


@router.post('/api/category/delete')
async def api_delete_category(request: Request, key: str = Form(...)):
    if not is_authed(request):
        return JSONResponse({'error': 'Unauthorized'}, 401)

    if key not in shared_data.PRODUCTS:
        return JSONResponse({'error': 'Kategori tidak ditemukan'}, 404)

    shared_data.PRODUCTS.pop(key, None)
    shared_data.save_products(shared_data.PRODUCTS)
    return JSONResponse({'ok': True})


@router.post('/api/item/add')
async def api_add_item(
    request: Request,
    cat_key: str = Form(...),
    item_id: str = Form(...),
    name: str = Form(...),
    duration: str = Form(...),
    price: str = Form(...),
):
    if not is_authed(request):
        return JSONResponse({'error': 'Unauthorized'}, 401)
    if cat_key not in shared_data.PRODUCTS:
        return JSONResponse({'error': 'Kategori tidak ditemukan'}, 400)
    if item_id in shared_data.ITEM_LOOKUP:
        return JSONResponse({'error': f'Item ID "{item_id}" sudah ada'}, 400)

    shared_data.PRODUCTS[cat_key]['items'].append({
        'id': item_id,
        'name': name,
        'duration': duration,
        'price': price,
        'notes': [],
    })
    shared_data.save_products(shared_data.PRODUCTS)
    return JSONResponse({'ok': True})


@router.post('/api/item/edit')
async def api_edit_item(
    request: Request,
    cat_key: str = Form(...),
    item_id: str = Form(...),
    name: str = Form(...),
    duration: str = Form(...),
    price: str = Form(...),
):
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
async def api_delete_item(
    request: Request,
    cat_key: str = Form(...),
    item_id: str = Form(...),
):
    if not is_authed(request):
        return JSONResponse({'error': 'Unauthorized'}, 401)
    if cat_key not in shared_data.PRODUCTS:
        return JSONResponse({'error': 'Kategori tidak ditemukan'}, 400)

    shared_data.PRODUCTS[cat_key]['items'] = [
        item for item in shared_data.PRODUCTS[cat_key]['items']
        if item['id'] != item_id
    ]
    shared_data.save_products(shared_data.PRODUCTS)
    return JSONResponse({'ok': True})


@router.post('/api/config/save')
async def api_save_config(
    request: Request,
    store_name: str = Form(...),
    wa_number: str = Form(...),
    idle_reset: int = Form(900),
):
    if not is_authed(request):
        return JSONResponse({'error': 'Unauthorized'}, 401)

    shared_data.save_config({
        'STORE_NAME': store_name,
        'WA_NUMBER': wa_number,
        'IDLE_RESET_SECONDS': max(idle_reset, 60),
    })
    return JSONResponse({'ok': True})


@router.post('/api/config/password')
async def api_change_password(
    request: Request,
    old_pass: str = Form(...),
    new_pass: str = Form(...),
):
    if not is_authed(request):
        return JSONResponse({'error': 'Unauthorized'}, 401)
    if password_managed_by_env():
        return JSONResponse({'error': 'Password dikelola dari environment dan tidak bisa diubah dari panel.'}, 400)
    if len(new_pass) < 8:
        return JSONResponse({'error': 'Password baru minimal 8 karakter.'}, 400)
    if not verify_admin_password(old_pass):
        return JSONResponse({'error': 'Password lama salah'}, 400)

    shared_data.save_config({
        'ADMIN_PASS_HASH': hash_password(new_pass),
        'ADMIN_PASS': '',
    })
    response = JSONResponse({'ok': True, 'message': 'Password berhasil diubah. Silakan login ulang.'})
    response.delete_cookie(SESSION_COOKIE_NAME, path=ADMIN_BASE_PATH)
    return response


@router.get('/api/export')
async def api_export(request: Request):
    if not is_authed(request):
        return JSONResponse({'error': 'Unauthorized'}, 401)

    exported_config = {
        key: value
        for key, value in shared_data.CONFIG.items()
        if key not in {'ADMIN_PASS', 'ADMIN_PASS_HASH'}
    }
    return JSONResponse({'products': shared_data.PRODUCTS, 'config': exported_config})

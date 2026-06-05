from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os

from app.core.auth import verify_login, create_session_token, make_session_value, require_auth, get_auth_or_none
from app.core.config import settings

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if get_auth_or_none(request):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if verify_login(username, password):
        token = create_session_token()
        cookie_val = make_session_value(token)
        response = RedirectResponse("/", status_code=302)
        response.set_cookie(
            "brooder_session",
            cookie_val,
            max_age=settings.SESSION_EXPIRE_HOURS * 3600,
            httponly=True,
            samesite="lax",
        )
        return response
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "نام کاربری یا رمز عبور اشتباه است"},
        status_code=401,
    )


@router.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("brooder_session")
    return response


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, auth=Depends(require_auth)):
    return templates.TemplateResponse("dashboard.html", {"request": request})

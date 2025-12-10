from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
import secrets
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# 設定固定的 SECRET_KEY（生產環境應使用環境變數）
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'furhub-secret-key-2024-pet-marketplace')

db = SQLAlchemy(app)

# -------------------------
# 允許的圖片格式
# -------------------------
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# -------------------------
# 使用者資料表
# -------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# -------------------------
# 商品資料表
# -------------------------
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200))
    store = db.Column(db.String(100))
    price = db.Column(db.String(50))
    category = db.Column(db.String(100))
    image = db.Column(db.String(300))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

# -------------------------
# 訂單資料表
# -------------------------
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer)
    buyer_location = db.Column(db.String(200))
    buyer_phone = db.Column(db.String(50))
    buyer_email = db.Column(db.String(100))

# -------------------------
# 寵物用品分類（單一分類，不需要讓使用者選擇）
# -------------------------
DEFAULT_CATEGORY = "寵物用品"

# -------------------------
# 登入驗證裝飾器
# -------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('請先登入', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# -------------------------
# 管理員驗證裝飾器
# -------------------------
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('請先登入', 'error')
            return redirect(url_for('login'))
        if not session.get('is_admin'):
            flash('您沒有權限執行此操作', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# -------------------------
# 首頁（含搜尋功能）
# -------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    q = request.args.get("q", "")

    query = Item.query

    if q:
        query = query.filter(Item.content.contains(q))

    items = query.order_by(Item.id.desc()).all()

    return render_template("index.html", items=items)

# -------------------------
# 使用者註冊
# -------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # 驗證
        if not username or not email or not password:
            flash('請填寫所有欄位', 'error')
            return render_template("register.html")

        if password != confirm_password:
            flash('密碼不一致', 'error')
            return render_template("register.html")

        if len(password) < 6:
            flash('密碼至少需要6個字元', 'error')
            return render_template("register.html")

        # 檢查使用者是否存在
        if User.query.filter_by(username=username).first():
            flash('使用者名稱已存在', 'error')
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash('Email 已被註冊', 'error')
            return render_template("register.html")

        # 建立使用者
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('註冊成功！請登入', 'success')
        return redirect(url_for('login'))

    return render_template("register.html")

# -------------------------
# 使用者登入
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            if user.is_admin:
                flash(f'歡迎回來，管理員 {user.username}！', 'success')
            else:
                flash(f'歡迎回來，{user.username}！', 'success')
            return redirect(url_for('index'))
        else:
            flash('使用者名稱或密碼錯誤', 'error')

    return render_template("login.html")

# -------------------------
# 使用者登出
# -------------------------
@app.route("/logout")
def logout():
    session.clear()
    flash('已成功登出', 'success')
    return redirect(url_for('index'))

# -------------------------
# 新增商品 (僅限管理員)
# -------------------------
@app.route("/add", methods=["GET", "POST"])
@admin_required
def add_item():
    if request.method == "POST":
        content = request.form.get("content", "").strip()
        store = request.form.get("store", "").strip()
        price = request.form.get("price", "").strip()

        # 驗證必填欄位
        if not content or not store or not price:
            flash('請填寫所有必填欄位', 'error')
            return render_template("add_item.html")

        # 處理圖片上傳
        if 'image' not in request.files:
            flash('請上傳商品圖片', 'error')
            return render_template("add_item.html")

        image_file = request.files["image"]

        if image_file.filename == '':
            flash('請選擇圖片檔案', 'error')
            return render_template("add_item.html")

        if not allowed_file(image_file.filename):
            flash('不支援的圖片格式，請使用 PNG、JPG、GIF 或 WebP', 'error')
            return render_template("add_item.html")

        # 安全處理檔名
        filename = secure_filename(image_file.filename)
        # 加上隨機字串避免檔名重複
        unique_filename = f"{secrets.token_hex(8)}_{filename}"
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
        image_file.save(image_path)

        # 建立商品
        item = Item(
            content=content,
            store=store,
            price=price,
            category=DEFAULT_CATEGORY,
            image=unique_filename,
            user_id=session.get('user_id')
        )
        db.session.add(item)
        db.session.commit()

        flash('商品上架成功！', 'success')
        return redirect("/")

    return render_template("add_item.html")

# -------------------------
# 商品詳細 + 購買頁面
# -------------------------
@app.route("/item/<int:item_id>")
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)
    return render_template("item_detail.html", item=item)

# -------------------------
# 下單
# -------------------------
@app.route("/buy/<int:item_id>", methods=["POST"])
def buy_item(item_id):
    location = request.form.get("location", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()

    # 驗證
    if not location or not phone or not email:
        flash('請填寫所有必填欄位', 'error')
        return redirect(url_for('item_detail', item_id=item_id))

    order = Order(
        item_id=item_id,
        buyer_location=location,
        buyer_phone=phone,
        buyer_email=email
    )
    db.session.add(order)
    db.session.commit()

    return render_template("order_success.html")

# -------------------------
# 刪除商品 (僅限管理員)
# -------------------------
@app.route("/delete/<int:item_id>", methods=["GET", "POST"])
@admin_required
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)

    # 刪除圖片檔案
    if item.image:
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], item.image)
        if os.path.exists(image_path):
            os.remove(image_path)

    db.session.delete(item)
    db.session.commit()

    flash('商品已刪除', 'success')
    return redirect("/")

# -------------------------
# 商品管理 (僅限管理員)
# -------------------------
@app.route("/my-items")
@admin_required
def my_items():
    # 管理員可以看到所有商品
    items = Item.query.order_by(Item.id.desc()).all()
    return render_template("my_items.html", items=items)

# -------------------------
# 訂單管理 (僅限管理員)
# -------------------------
@app.route("/orders")
@admin_required
def orders():
    # 管理員可以看到所有訂單
    orders_list = Order.query.all()

    # 組合訂單資料
    orders_data = []
    for order in orders_list:
        item = Item.query.get(order.item_id)
        if item:
            orders_data.append({
                'order': order,
                'item': item
            })

    return render_template("orders.html", orders=orders_data)

# -------------------------
# 圖片路徑
# -------------------------
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# -------------------------
# 錯誤處理
# -------------------------
@app.errorhandler(404)
def not_found_error(error):
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template("500.html"), 500

# -------------------------
# 建立預設管理員帳號
# -------------------------
def create_default_admin():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@curated.com',
            is_admin=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('預設管理員帳號已建立：')
        print('  帳號：admin')
        print('  密碼：admin123')
    return admin

# -------------------------
# 初始化展示商品資料
# -------------------------
def seed_demo_products():
    # 如果已有商品就不重複建立
    if Item.query.count() > 0:
        return

    admin = User.query.filter_by(username='admin').first()
    admin_id = admin.id if admin else None

    products = [
        {"content": "自動伸縮寵物牽繩 5米 - 舒適防滑握把 一鍵鎖定", "store": "FurHub 官方商城", "price": "399", "image": "d11cc63cf52e0c9e.png"},
        {"content": "智能自動拋球機 - 狗狗互動訓練玩具 3段距離調節", "store": "FurHub 官方商城", "price": "1280", "image": "ec5834f792e018b8.png"},
        {"content": "Greenies 健綠潔牙骨 原味 Regular 中型犬適用 12入", "store": "FurHub 官方商城", "price": "450", "image": "efaceca171ec65f4.png"},
        {"content": "Milk-Bone 牛奶骨狗狗餅乾 潔牙零食 酥脆口感", "store": "FurHub 官方商城", "price": "320", "image": "b52be015fa732b09.png"},
        {"content": "自動清潔寵物除毛梳 - 一鍵清除浮毛 不傷皮膚 適用各種毛髮", "store": "FurHub 官方商城", "price": "289", "image": "pet_brush_01.jpg"},
        {"content": "保暖羊羔絨寵物毛衣 - 附D環牽繩孔 三色可選 (灰/藍/棕)", "store": "FurHub 官方商城", "price": "459", "image": "pet_sweater_01.jpg"},
        {"content": "竹木架高寵物碗架組 - 雙碗設計 護頸斜面 貓狗適用", "store": "FurHub 官方商城", "price": "680", "image": "pet_bowl_stand_01.jpg"},
        {"content": "半封閉式貓砂盆 - 時尚白灰雙色 防濺設計 大空間好清理", "store": "FurHub 官方商城", "price": "890", "image": "cat_litter_box_01.jpg"},
        {"content": "PETSTRO 三輪寵物推車 - 透氣網窗 可折疊收納 承重25kg", "store": "FurHub 官方商城", "price": "2480", "image": "pet_stroller_01.jpg"},
        {"content": "舒適絨毛寵物窩床 - 骨頭圖案 可拆洗 中大型犬適用", "store": "FurHub 官方商城", "price": "750", "image": "pet_bed_01.jpg"},
        {"content": "寵物專用紙尿褲 - 超強吸收 防側漏 生理期/外出必備 M號12入", "store": "FurHub 官方商城", "price": "320", "image": "pet_diaper_01.jpg"},
        {"content": "Portland Pet Food 手工狗零食組合 - 薑餅人/培根/南瓜餅乾 天然無穀", "store": "FurHub 官方商城", "price": "580", "image": "dog_treats_combo_01.jpg"},
        {"content": "Cesar 西莎狗罐頭 - 牛肉起司時蔬凍 100g 單入", "store": "FurHub 官方商城", "price": "45", "image": "cesar_dog_food_01.jpg"},
        {"content": "專業寵物指甲剪 - 不鏽鋼刀頭 安全鎖扣 貓狗通用", "store": "FurHub 官方商城", "price": "199", "image": "pet_nail_clipper_01.jpg"},
        {"content": "有機雞肉牛皮捲零食 - 天然無添加 潔牙磨牙 300g大包裝", "store": "FurHub 官方商城", "price": "420", "image": "rawhide_sticks_01.jpg"},
    ]

    for p in products:
        item = Item(
            content=p["content"],
            store=p["store"],
            price=p["price"],
            category=DEFAULT_CATEGORY,
            image=p["image"],
            user_id=admin_id
        )
        db.session.add(item)

    db.session.commit()
    print(f'已載入 {len(products)} 個展示商品')

# -------------------------
# 初始化資料庫 (Vercel 需要在 import 時執行)
# -------------------------
def init_db():
    if not os.path.exists(Config.UPLOAD_FOLDER):
        os.makedirs(Config.UPLOAD_FOLDER)
    db.create_all()
    create_default_admin()
    seed_demo_products()

# Vercel serverless 環境初始化
with app.app_context():
    init_db()

# -------------------------
# 本地開發伺服器
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)

from app import create_app, db
import os

app = create_app()

# 确保应用上下文内创建数据库表
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
from app.models import Group, File, FileVersion
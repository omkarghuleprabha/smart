from flask import Blueprint, request, redirect, url_for, flash, session, current_app
from werkzeug.utils import secure_filename
from app.models import db, Complaint
import os
import uuid

complaint_bp = Blueprint('complaint_bp', __name__, url_prefix='/complaint')


@complaint_bp.route('/add', methods=['POST'])
def add_complaint():
    # 🔐 Check login
    if 'user_id' not in session:
        flash("Please login first", "warning")
        return redirect(url_for('auth_bp.login'))

    # 📥 Get form data
    title = request.form.get('title')
    description = request.form.get('description')
    district = request.form.get('district')
    taluka = request.form.get('taluka')
    village = request.form.get('village')
    priority = request.form.get('priority')
    file = request.files.get('garbage_img')

    # ✅ Validation
    if not all([title, description, district, taluka, village, file]):
        flash("All fields are required!", "danger")
        return redirect(url_for('auth_bp.citizen_dashboard'))

    # 📸 File Upload Handling
    try:
        filename = secure_filename(file.filename)

        if '.' in filename:
            ext = filename.rsplit('.', 1)[1].lower()
        else:
            ext = 'jpg'

        unique_filename = f"{uuid.uuid4().hex}.{ext}"

        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'complaints')

        # create folder if not exists
        os.makedirs(upload_folder, exist_ok=True)

        file.save(os.path.join(upload_folder, unique_filename))

    except Exception as e:
        flash(f"File upload error: {str(e)}", "danger")
        return redirect(url_for('auth_bp.citizen_dashboard'))

    # 🗄️ Save to DB
    try:
        new_complaint = Complaint(
            ticket_id=f"TKT-{uuid.uuid4().hex[:8].upper()}",
            citizen_id=session['user_id'],
            title=title,
            description=description,
            district=district,
            taluka=taluka,
            village=village,
            image_path=unique_filename,
            priority=priority,
            status='pending'
        )

        db.session.add(new_complaint)
        db.session.commit()

        flash(f"Complaint submitted! Ticket ID: {new_complaint.ticket_id}", "success")

    except Exception as e:
        db.session.rollback()
        print("DB ERROR:", e)
        flash("Database error! Check model or DB connection.", "danger")

    return redirect(url_for('auth_bp.citizen_dashboard'))
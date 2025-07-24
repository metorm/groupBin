from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from app import db
from app.models import Group
import datetime 
import uuid

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html', datetime=datetime)


@main.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

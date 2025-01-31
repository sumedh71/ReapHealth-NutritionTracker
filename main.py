from dataclasses import dataclass

from flask import Flask, render_template, request, redirect, send_file, url_for
import numpy as np
import matplotlib.pyplot as plt
import requests
from io import BytesIO
from dotenv import load_dotenv
import os

app = Flask(__name__)

nut_api_key = os.getenv('NUT_API_KEY')
nut_app_id = os.getenv('NUT_APP_ID')
recipe_api_key = os.getenv('RECIPE_API_KEY')

food_today = []

calorie_goal = 0
protein_goal = 0
fat_goal = 0
carbs_goal = 0


@dataclass
class Food:
    name: str
    calories: int
    protein: int
    fat: int
    carbs: int


CALORIE_GOAL_LIMIT = 3200  # kcal
DEFAULT_PROTEIN_GOAL = 180  # gram
DEFAULT_FAT_GOAL = 80  #gram
DEFAULT_CARBS_GOAL = 300  #gram


def get_nutritional_info(food_name, portion):
    url = "https://trackapi.nutritionix.com/v2/natural/nutrients"
    headers = {
        'x-app-id': nut_app_id,
        'x-app-key': nut_api_key,
        'Content-Type': 'application/json'
    }
    data = {'query': f"{portion} {food_name}"}
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()
    else:
        print("Error retrieving nutritional information")
    return None


def get_recipe_suggestions(missing_nutrient):
    url = f"https://api.spoonacular.com/recipes/complexSearch?query={missing_nutrient}&apiKey={recipe_api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print("Error retrieving recipes")
    return None


@app.route('/')
def home():
    return render_template('index.html', food_today=food_today)


@app.route('/add_food_manual', methods=['POST'])
def add_food_manual():
    foodname = request.form['name']
    calories = int(request.form['calories'])
    protein = int(request.form['protein'])
    fat = int(request.form['fat'])
    carbs = int(request.form['carbs'])
    food = Food(foodname, calories, protein, fat, carbs)
    food_today.append(food)
    return redirect(url_for('home'))


@app.route('/add_food_auto', methods=['POST'])
def add_food_auto():
    food_name = request.form['name']
    portion = request.form['portion']
    nutritional_info = get_nutritional_info(food_name, portion)
    if nutritional_info:
        nutrients = nutritional_info['foods'][0]
        calories = nutrients['nf_calories']
        protein = nutrients['nf_protein']
        fat = nutrients['nf_total_fat']
        carbs = nutrients['nf_total_carbohydrate']
        food = Food(food_name, calories, protein, fat, carbs)
        food_today.append(food)
    return redirect(url_for('home'))


@app.route('/get-goals', methods=['GET', 'POST'])
def get_goals():
    global calorie_goal, protein_goal, fat_goal, carbs_goal
    
    if request.method == 'POST':
        use_default = request.form.get('use_default')
        if use_default == 'yes':
            calorie_goal = CALORIE_GOAL_LIMIT
            protein_goal = DEFAULT_PROTEIN_GOAL
            fat_goal = DEFAULT_FAT_GOAL
            carbs_goal = DEFAULT_CARBS_GOAL
        else:
            calorie_goal = int(request.form['calories'])
            protein_goal = int(request.form['protein'])
            fat_goal = int(request.form['fat'])
            carbs_goal = int(request.form['carbs'])

        return redirect(url_for('home'))
    ##return render_template('get_goals.html')


@app.route('/visualize_progress', methods=['GET'])
def visualize_progress():
    if food_today != []:
        calorie_sum = sum(food.calories for food in food_today)
        protein_sum = sum(food.protein for food in food_today)
        fat_sum = sum(food.fat for food in food_today)
        carbs_sum = sum(food.carbs for food in food_today)
        fig, axs = plt.subplots(2, 2)

        axs[0, 0].pie([protein_sum, fat_sum, carbs_sum],
                      labels=["Proteins", "Fats", "Carbs"],
                      autopct="%1.1f%%")
        axs[0, 0].set_title("Distribution of Macronutrients")
        axs[0, 1].bar([0, 1, 2], [protein_sum, fat_sum, carbs_sum], width=0.4)
        axs[0, 1].bar([0.5, 1.5, 2.5], [protein_goal, fat_goal, carbs_goal],
                      width=0.4)
        axs[0, 1].set_title("Progress of Macronutrients")
        axs[1, 0].pie([calorie_sum, calorie_goal - calorie_sum],
                      labels=["Calories", "Remaining"],
                      autopct="%1.1f%%")
        axs[1, 0].set_title("Calories Goal Progress")
        axs[1, 1].plot(list(range(len(food_today))),
                       np.cumsum([food.calories for food in food_today]),
                       label="Calories Consumed")
        axs[1, 1].plot(list(range(len(food_today))),
                       [calorie_goal] * len(food_today),
                       label="Calorie Goal")
        axs[1, 1].legend()
        axs[1, 1].set_title("Calories Goal Over Time")
        fig.tight_layout()

        img = BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)
        plt.close(fig)

        return send_file(img, mimetype='image/png')

    #else:
        #return send_file(BytesIO(), mimetype='image/png')


@app.route('/get_recipes', methods=['GET'])
def get_recipes():
    global calorie_goal, protein_goal, fat_goal, carbs_goal
    
    if food_today:
        protein_sum = sum(food.protein for food in food_today)
        fat_sum = sum(food.fat for food in food_today)
        carbs_sum = sum(food.carbs for food in food_today)

        missing_nutrients = []
        if protein_sum < protein_goal:
            missing_nutrients.append('protein')
        if fat_sum < fat_goal:
            missing_nutrients.append('fat')
        if carbs_sum < carbs_goal:
            missing_nutrients.append('carbs')

        results = ""
        if missing_nutrients:
            for nutrient in missing_nutrients:
                recipes = get_recipe_suggestions(nutrient)
                if recipes:
                    results += f"Suggested recipes to increase your {nutrient} intake:\n"
                    for recipe in recipes['results']:
                        results += f"- {recipe['title']} (link: {recipe.get('sourceURL', 'link not available')})\n"
                else:
                    results += f"No recipes available for {nutrient} at the moment!"

            return render_template('get_recipes.html', results=results)

        else:
            return render_template('get_recipes.html',
                                   results="All goals met!")
    else:
        return redirect(url_for('get_goals'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)


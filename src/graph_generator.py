import matplotlib.pyplot as plt
import numpy as np
import os

def create_radar_chart(student_name, student_data, class_averages, output_dir):
    labels = list(student_data.keys())
    if not labels: return None

    student_scores = [student_data[l]['average'] for l in labels]
    class_scores = [class_averages.get(l, 0) for l in labels]

    num_vars = len(labels)
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()

    student_scores += [student_scores[0]]
    class_scores += [class_scores[0]]
    angles += [angles[0]]
    labels += [labels[0]]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    plt.xticks(angles[:-1], labels[:-1])
    ax.set_rlabel_position(0)
    plt.yticks([20, 40, 60, 80], ["20", "40", "60", "80"], color="grey", size=7)
    plt.ylim(0, 100)

    ax.plot(angles, class_scores, color='red', linewidth=2, linestyle='solid', label='Class Avg')
    ax.fill(angles, class_scores, color='red', alpha=0.1)

    ax.plot(angles, student_scores, color='blue', linewidth=2, linestyle='solid', label='Student')
    ax.fill(angles, student_scores, color='blue', alpha=0.25)

    plt.title(f"Profile: {student_name}", size=15, color='black', y=1.1)
    plt.legend(loc='upper right', bbox_to_anchor=(1.1, 1.1))

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    safe_name = "".join([c for c in student_name if c.isalnum() or c==' ']).strip()
    filename = f"{output_dir}/{safe_name}_radar.png"
    plt.savefig(filename)
    plt.close()
    return filename

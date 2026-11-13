"""Nearest centroid of the k=3 skill clusters. Ratings are not scaled."""

# skill_programming, skill_data_stats, skill_frontend_design, skill_business_pitch
CENTROIDS = (
    (2.923076923076923, 3.076923076923077, 2.8461538461538463, 4.0),
    (3.0, 3.6, 1.4, 1.6),
    (4.2, 4.6, 4.0, 4.6),
)


def predict_cluster(skills):
    """Return the label of the nearest centroid for four skill ratings."""
    nearest = 0
    nearest_distance = None
    for label, centroid in enumerate(CENTROIDS):
        distance = 0.0
        for rating, center in zip(skills, centroid):
            gap = rating - center
            distance += gap * gap
        if nearest_distance is None or distance < nearest_distance:
            nearest = label
            nearest_distance = distance
    return nearest

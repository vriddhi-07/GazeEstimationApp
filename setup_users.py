from django.contrib.auth.models import User, Group

# Create the three target groups
group1, _ = Group.objects.get_or_create(name="Set 1")
group2, _ = Group.objects.get_or_create(name="Set 2")
group3, _ = Group.objects.get_or_create(name="Set 3")

# Define cohorts mapping username to group
cohorts = {
    group1: ['1', '2', '3', '4'],
    group2: ['5', '6', '7', '8'],
    group3: ['9', '10', '11', '12']
}

# Create users and assign to groups
for group, usernames in cohorts.items():
    for username in usernames:
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.set_password('survey2026') # Set a universal password here
            user.save()
        user.groups.add(group)
        print(f"User {username} added to {group.name}")
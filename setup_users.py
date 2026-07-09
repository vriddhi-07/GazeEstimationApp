from django.contrib.auth.models import User, Group

# Create the three target groups
group1, _ = Group.objects.get_or_create(name="Set 1")
group2, _ = Group.objects.get_or_create(name="Set 2")
group3, _ = Group.objects.get_or_create(name="Set 3")

# Define cohorts mapping username to group.
# Original 4-per-group accounts (1-12) and the 13-27 batch are left exactly
# as they were — some may already have ParticipantSession/recording data
# tied to them. 28, 29, 30 added one per group (10/10/10 = 30 total, using
# up the full 30 RealEye licenses including the 3 originally set aside as
# trials — adjust here later if those 3 need to stay reserved instead).
cohorts = {
    group1: ['1', '2', '3', '4', '13', '14', '15', '16', '17', '28','31','32'],
    group2: ['5', '6', '7', '8', '18', '19', '20', '21', '22', '29','33','34'],
    group3: ['9', '10', '11', '12', '23', '24', '25', '26', '27', '30','35','36']
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
# Strats

## Les actions les plus payantes (Ore) : 

1. Pick up Blitzium Cores
2. Clean Radiant Cores
3. Pick up Blitzium Ingot
4. Clean Radiant Slag
5. Pick up Blitzium Nugget

## Répartitions des cars

For 1-2 Cars:

Focus on defensive play since you have limited resources
Prioritize collecting blitzium_core (5 points) while avoiding radiant materials entirely
Use your limited cars to patrol a smaller, defensible territory rather than trying to cover the whole map
When carrying valuable cores, take safer but longer routes to avoid interception

For 3-4 Cars:

Implement a "buddy system" where cars work in pairs
One car can act as a defender/interceptor while its partner collects resources
Dedicate 1-2 cars specifically for disrupting opponent collection patterns
The 20-turn respawn penalty makes car preservation crucial, so avoid risky interceptions unless the point trade is clearly favorable

For 5-6 Cars:

You can now implement a more complex strategy with specialized roles:

2 cars for pure collection (focusing on cores and ingots)
2 cars for territorial control and interception
1-2 cars for strategic disruption of opponent patterns or as "flex" positions


Consider sacrificing one car for a high-value interception, as you have enough remaining cars to maintain map control during the respawn penalty
Create "zones of control" where multiple cars can support each other

## Exemple d'implementation de Claude :

```Python
class Car:
    def __init__(self, position, cargo_capacity=3):
        self.position = position
        self.cargo = []
        self.cargo_capacity = cargo_capacity
        self.respawn_timer = 0
        
    def is_active(self):
        return self.respawn_timer == 0
        
    def has_space(self):
        return len(self.cargo) < self.cargo_capacity

class StrategyV0:
    def __init__(self, num_cars):
        self.num_cars = num_cars
        self.ore_values = {
            "blitzium_core": 5,
            "blitzium_ingot": 3,
            "blitzium_nugget": 1,
            "radiant_core": -5,
            "radiant_slag": -2
        }
        
    def assign_roles(self):
        """Assign basic roles based on number of cars available"""
        if self.num_cars <= 2:
            return {"collectors": self.num_cars, "defenders": 0}
        elif self.num_cars <= 4:
            return {
                "collectors": self.num_cars - 1,
                "defenders": 1
            }
        else:
            return {
                "collectors": self.num_cars - 2,
                "defenders": 2
            }
    
    def should_grab(self, car, ore_type, nearby_enemies=0):
        """Decide whether to grab an ore"""
        # Don't grab if cargo is full
        if not car.has_space():
            return False
            
        # Basic value calculation
        ore_value = self.ore_values[ore_type]
        
        # Don't grab negative value ores in V0
        if ore_value < 0:
            return False
            
        # If enemies are nearby, only grab high-value ores
        if nearby_enemies > 0:
            return ore_value >= 3  # Only grab cores and ingots when threatened
            
        return True
    
    def should_drop(self, car, nearby_enemies=0):
        """Decide whether to drop cargo"""
        if not car.cargo:
            return False
            
        # Drop if enemies are nearby and we're carrying valuable cargo
        if nearby_enemies > 0:
            cargo_value = sum(self.ore_values[ore] for ore in car.cargo)
            return cargo_value >= 3
            
        # In V0, only drop when cargo is full
        return len(car.cargo) >= car.cargo_capacity
    
    def should_intercept(self, car, enemy_cargo=[]):
        """Decide whether to attempt interception"""
        if not car.is_active():
            return False
            
        # Calculate potential value gain from interception
        enemy_value = sum(self.ore_values[ore] for ore in enemy_cargo)
        
        # In V0, only intercept if enemy has valuable cargo (3 or more points)
        return enemy_value >= 3
    
    def get_priority_target(self, visible_ores):
        """Determine which ore to prioritize collecting"""
        priority_order = ["blitzium_core", "blitzium_ingot", "blitzium_nugget"]
        
        for ore_type in priority_order:
            if ore_type in visible_ores:
                return ore_type
        
        return None

    def update_strategy(self, game_state):
        """Update strategy based on game state"""
        roles = self.assign_roles()
        
        # Basic strategy adjustments based on game phase
        if game_state.get('time_remaining', 100) < 30:  # Late game
            # Become more aggressive in the late game
            roles['defenders'] = min(1, roles['defenders'])  # Reduce defenders
            roles['collectors'] = self.num_cars - roles['defenders']  # Increase collectors
        
        return roles
```
import random as r

level = 1  #10 Levels of Difficulty, 20 actions in each
reset_button = 0
score = 0

class OrderStateMachine:
    def __init__(self):
        self.states = {
            "attack": self.attack_state,
            "block": self.block_state,
            "force": self.force_state,
            "power": self.power_state,
            "reset": self.reset_state,
        }
        self.current_state = "power-on"

    def transition(self, event):
        if event in ['attack', 'block', 'force', 'power', 'reset']:
            self.current_state = self.states[self.current_state](event)
        else:
            print(f"Invalid event: {event}")

    def attack_state(self, event):
        if reset_button:
            self.current_state = "reset"
        else:
            self.current_state = self.random_state_generator()
        return self.current_state

    def block_state(self, event):
        if reset_button:
            self.current_state = "reset"
        else:
            self.current_state = self.random_state_generator()
        return self.current_state

    def force_state(self, event):
        if reset_button:
            self.current_state = "reset"
        else:
            self.current_state = self.random_state_generator()
        return self.current_state
    
    def power_state(self, event):
        if reset_button:
            self.current_state = "reset"
        else:
            self.current_state = self.random_state_generator()
        return self.current_state
    
    def reset_state(self, event):
        level = 1
        score = 0
        return self.current_state
    
    def random_state_generator(self):
        num  = r.randint(0,2)
        if num == 0:
            random_state = "Attack"
        elif num == 1:
            random_state = "Block"
        else:
            random_state = "Force"
        return random_state

# Example usage
order_machine = OrderStateMachine()
order_machine.transition("payment_received")
order_machine.transition("item_shipped")
print(f"Current state: {order_machine.current_state}")

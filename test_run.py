import pygame
import main

# Run 100 frames to ensure no syntax errors and the game loop logic functions correctly without crashing
pygame.init()
screen = pygame.display.set_mode((800, 400))
game = main.Game()
game.state = "PLAYING"

for i in range(100):
    game.update()
    game.draw(screen)

print("Game loop simulated successfully!")

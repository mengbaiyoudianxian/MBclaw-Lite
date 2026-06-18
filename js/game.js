// MBclaw-Lite Game Logic
class ClawMachine {
    constructor() {
        this.score = 0;
        this.attempts = 3;
        this.clawPosition = { x: 50, y: 20 }; // percentage from left, pixels from top
        this.isGrabbing = false;
        this.prizes = [];
        this.gameArea = document.querySelector('.machine-glass');
        this.clawContainer = document.querySelector('.claw-container');
        this.claw = document.querySelector('.claw');
        this.prizesContainer = document.querySelector('.prizes');
        
        this.init();
    }
    
    init() {
        this.generatePrizes();
        this.setupEventListeners();
        this.updateUI();
        this.renderClawPosition();
    }
    
    generatePrizes() {
        const prizeTypes = ['🎁', '🧸', '🎮', '🎨', '🎵', '📱', '🎧', '📷', '🔮', '💎'];
        const numPrizes = 8;
        
        for (let i = 0; i < numPrizes; i++) {
            const prize = {
                id: i,
                type: prizeTypes[Math.floor(Math.random() * prizeTypes.length)],
                x: Math.random() * 80 + 10, // 10% to 90% width
                y: Math.random() * 60 + 20, // 20% to 80% height
                collected: false
            };
            this.prizes.push(prize);
        }
        
        this.renderPrizes();
    }
    
    renderPrizes() {
        this.prizesContainer.innerHTML = '';
        
        this.prizes.forEach(prize => {
            if (!prize.collected) {
                const prizeElement = document.createElement('div');
                prizeElement.className = 'prize';
                prizeElement.textContent = prize.type;
                prizeElement.style.left = `${prize.x}%`;
                prizeElement.style.bottom = `${prize.y}px`;
                prizeElement.style.animationDelay = `${Math.random() * 2}s`;
                this.prizesContainer.appendChild(prizeElement);
            }
        });
    }
    
    setupEventListeners() {
        // Button controls
        document.getElementById('moveLeft').addEventListener('click', () => this.moveClaw(-5, 0));
        document.getElementById('moveRight').addEventListener('click', () => this.moveClaw(5, 0));
        document.getElementById('moveUp').addEventListener('click', () => this.moveClaw(0, -10));
        document.getElementById('moveDown').addEventListener('click', () => this.moveClaw(0, 10));
        document.getElementById('grabBtn').addEventListener('click', () => this.grab());
        
        // Keyboard controls
        document.addEventListener('keydown', (e) => {
            switch(e.key) {
                case 'ArrowLeft':
                case 'a':
                case 'A':
                    this.moveClaw(-5, 0);
                    break;
                case 'ArrowRight':
                case 'd':
                case 'D':
                    this.moveClaw(5, 0);
                    break;
                case 'ArrowUp':
                case 'w':
                case 'W':
                    this.moveClaw(0, -10);
                    break;
                case 'ArrowDown':
                case 's':
                case 'S':
                    this.moveClaw(0, 10);
                    break;
                case ' ':
                    e.preventDefault();
                    this.grab();
                    break;
            }
        });
    }
    
    moveClaw(dx, dy) {
        if (this.isGrabbing) return;
        
        this.clawPosition.x = Math.max(10, Math.min(90, this.clawPosition.x + dx));
        this.clawPosition.y = Math.max(20, Math.min(200, this.clawPosition.y + dy));
        
        this.renderClawPosition();
    }
    
    renderClawPosition() {
        this.clawContainer.style.left = `${this.clawPosition.x}%`;
        this.clawContainer.style.top = `${this.clawPosition.y}px`;
    }
    
    grab() {
        if (this.isGrabbing || this.attempts <= 0) return;
        
        this.isGrabbing = true;
        this.attempts--;
        
        // Animate claw dropping
        const originalY = this.clawPosition.y;
        this.clawPosition.y = 180;
        this.renderClawPosition();
        
        // Close claw fingers
        setTimeout(() => {
            this.claw.querySelector('.claw-finger.left').style.transform = 'rotate(5deg)';
            this.claw.querySelector('.claw-finger.right').style.transform = 'rotate(-5deg)';
        }, 500);
        
        // Check for prize collection
        setTimeout(() => {
            this.checkPrizeCollection();
            
            // Return claw to original position
            setTimeout(() => {
                this.clawPosition.y = originalY;
                this.renderClawPosition();
                
                // Open claw fingers
                setTimeout(() => {
                    this.claw.querySelector('.claw-finger.left').style.transform = 'rotate(15deg)';
                    this.claw.querySelector('.claw-finger.right').style.transform = 'rotate(-15deg)';
                    this.isGrabbing = false;
                    this.updateUI();
                    
                    // Check if game is over
                    if (this.attempts <= 0) {
                        setTimeout(() => {
                            alert(`Game Over! Final Score: ${this.score}`);
                            this.resetGame();
                        }, 500);
                    }
                }, 300);
            }, 300);
        }, 1000);
    }
    
    checkPrizeCollection() {
        const clawRect = this.claw.getBoundingClientRect();
        const gameRect = this.gameArea.getBoundingClientRect();
        
        // Convert claw position to relative coordinates
        const clawX = (clawRect.left + clawRect.width / 2 - gameRect.left) / gameRect.width * 100;
        const clawY = (clawRect.top + clawRect.height - gameRect.top) / gameRect.height * 100;
        
        let collected = false;
        
        this.prizes.forEach(prize => {
            if (!prize.collected) {
                const distance = Math.sqrt(
                    Math.pow(clawX - prize.x, 2) + 
                    Math.pow(clawY - prize.y, 2)
                );
                
                // If close enough (within 15 units)
                if (distance < 15) {
                    prize.collected = true;
                    this.score += 100;
                    collected = true;
                    
                    // Add collection effect
                    this.showCollectionEffect(prize.x, prize.y);
                }
            }
        });
        
        if (collected) {
            this.renderPrizes();
        }
    }
    
    showCollectionEffect(x, y) {
        const effect = document.createElement('div');
        effect.className = 'collection-effect';
        effect.textContent = '+100';
        effect.style.left = `${x}%`;
        effect.style.bottom = `${y}px`;
        
        this.gameArea.appendChild(effect);
        
        setTimeout(() => {
            effect.remove();
        }, 1000);
    }
    
    updateUI() {
        document.getElementById('scoreValue').textContent = this.score;
        document.getElementById('attemptsValue').textContent = this.attempts;
    }
    
    resetGame() {
        this.score = 0;
        this.attempts = 3;
        this.clawPosition = { x: 50, y: 20 };
        this.isGrabbing = false;
        this.prizes = [];
        
        this.generatePrizes();
        this.updateUI();
        this.renderClawPosition();
    }
}

// CSS for collection effect
const style = document.createElement('style');
style.textContent = `
    .collection-effect {
        position: absolute;
        color: #2ecc71;
        font-weight: bold;
        font-size: 1.2rem;
        animation: collectEffect 1s ease-out forwards;
        pointer-events: none;
        z-index: 100;
    }
    
    @keyframes collectEffect {
        0% {
            opacity: 1;
            transform: translateY(0);
        }
        100% {
            opacity: 0;
            transform: translateY(-50px);
        }
    }
`;
document.head.appendChild(style);

// Initialize game when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const game = new ClawMachine();
});
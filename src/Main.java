import java.util.Scanner;

public class Main {

	Scanner scanner = new Scanner(System.in);
	boolean isRunning = true;
	String name;
	String klass;
	Player player;
	Fight fight = new Fight();

	Input input = new Input();

	public Main(){
		init();
		gameLoop();
	}

	public static void main(String[] args) {
		new Main();
	}

	public void init(){

		System.out.println("Welcome to svantrenish rpg!");

		System.out.print("Please tell me, what is your name?: ");
		
		name = scanner.nextLine();
		
		System.out.print("Tell me, do you wish to be a fighter or a tank? ");
		klass = scanner.nextLine();


		if(klass.equals("fighter")){
			player = new Player(100, 15, name, klass);
		}else if(klass.equals("tank")){
			player = new Player(120, 10, name, klass);
		}else{
			System.out.println("invalid input!");
		}
		
		System.out.println("Hello " + name + ", i see that you choose to be a " + klass);

	}

	public void gameLoop(){
		while(isRunning){
			update();
		}
	}

	public void update(){
		
		input.normalInput();
		switch(input.choise){
		case 1:
			player.displayStats();
			break;
		case 2:
			fight.fight(player, new GiantRat());
			break;
		default:
			System.out.println("Invalid command!");
		}
	}

}

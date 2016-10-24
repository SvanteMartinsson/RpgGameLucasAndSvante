import java.util.LinkedList;
import java.util.Random;
import java.util.Scanner;

public class Main {

	
	LinkedList<GameObject> enemies = new LinkedList<GameObject>();
	Scanner scanner = new Scanner(System.in);
	boolean isRunning = true;
	String name;
	String klass;
	Player player;
	Fight fight = new Fight();
	
	Random r = new Random();
	
	int ranE;

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
			System.exit(0);
		}
		
		System.out.println("Hello " + name + ", i see that you choose to be a " + klass);
		
		player.xp = 95;

	}

	public void gameLoop(){
		while(isRunning){
			update();
		}
	}

	public void update(){
		
		
		enemies.add(new GiantRat());
		enemies.add(new CaveBear());
		enemies.add(new Undead());
		
		
		player.update();
		
		input.normalInput();
		switch(input.choise){
		case 1:
			player.displayStats();
			break;
		case 2:
			ranE = r.nextInt(2) + 1;
			
			fight.fight(player, enemies.get(ranE));
			break;
		default:
			System.out.println("Invalid command!");
		}
		
		for(int i = 0; i<enemies.size(); i++){
			enemies.remove(i);
		}
	}

}

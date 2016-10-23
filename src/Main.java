import java.util.Scanner;

public class Main {

	Scanner scanner = new Scanner(System.in);
	boolean isRunning = true;
	String name;
	String sex;
	Player player;

	Input input = new Input();

	public Main(){
		init();
		gameLoop();
	}

	public static void main(String[] args) {
		new Main();
	}

	public void init(){

		System.out.println("Welcome svantish rpg!");
		System.out.print("Tell me, are you a boy or a girl?: ");

		sex = scanner.nextLine();

		System.out.print("That's nice! Now please tell me, what is your name?: ");

		name = scanner.nextLine();

		if(sex.equals("boy")){
			player = new Player(100, 15, name, sex);
		}else{
			player = new Player(1, 10, name, sex);
		}

		System.out.println("Hello " + name + "i see that you're a " + sex);

		player.addToInv("Knife");

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
			player.displayInv();
			break;
		case 2:
			//Enter dungeon code here
			break;
		default:
			System.out.println("Invalid command!");
		}
	}

}
